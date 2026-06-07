# Main Terraform configuration for District Award Travel Infrastructure
# Managed by Mitchell Hashimoto - Infrastructure Engineer

terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "district-award-travel-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-lock-table"
  }
}

provider "aws" {
  region = var.aws_region
}

# Create VPC for District Award Travel
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "district-award-travel-vpc"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = var.private_subnets
  public_subnets  = var.public_subnets

  enable_nat_gateway = true
  single_nat_gateway = true
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Environment = var.environment
    Project     = "District Award Travel"
    ManagedBy   = "Terraform"
  }
}

# Security Group for Application Servers
resource "aws_security_group" "app_sg" {
  name        = "district-award-travel-app-sg"
  description = "Security group for application servers"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.admin_cidr_blocks
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "district-award-travel-app-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Security Group for Database
resource "aws_security_group" "db_sg" {
  name        = "district-award-travel-db-sg"
  description = "Security group for RDS database"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "district-award-travel-db-sg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# IAM Role for EC2 Instances
resource "aws_iam_role" "app_role" {
  name = "district-award-travel-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "app_profile" {
  name = "district-award-travel-app-profile"
  role = aws_iam_role.app_role.name
}

# IAM Policy for S3 Access (for award travel data)
resource "aws_iam_policy" "s3_access_policy" {
  name        = "district-award-travel-s3-access-policy"
  description = "Policy for accessing award travel data in S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject"
        ],
        Effect   = "Allow",
        Resource = [
          "arn:aws:s3:::district-award-travel-data",
          "arn:aws:s3:::district-award-travel-data/*"
        ]
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "s3_access_attachment" {
  role       = aws_iam_role.app_role.name
  policy_arn = aws_iam_policy.s3_access_policy.arn
}

# Launch Template for Application Servers
resource "aws_launch_template" "app_launch_template" {
  name_prefix   = "district-award-travel-app-"
  image_id      = var.ami_id
  instance_type = var.instance_type
  key_name      = var.key_name

  iam_instance_profile {
    name = aws_iam_instance_profile.app_profile.name
  }

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [aws_security_group.app_sg.id]
  }

  user_data = base64encode(<<-EOF
              #!/bin/bash
              # Bootstrap script for District Award Travel application servers

              # Update system
              apt-get update -y
              apt-get upgrade -y

              # Install Docker
              apt-get install -y docker.io docker-compose
              systemctl enable docker
              systemctl start docker

              # Install CloudWatch Agent for monitoring
              wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
              dpkg -i -E ./amazon-cloudwatch-agent.deb

              # Configure CloudWatch
              cat > /opt/aws/amazon-cloudwatch-agent/bin/config.json <<EOL
              {
                "logs": {
                  "logs_collected": {
                    "files": {
                      "collect_list": [
                        {
                          "file_path": "/var/log/app.log",
                          "log_group_name": "district-award-travel-app-logs",
                          "log_stream_name": "{instance_id}"
                        }
                      ]
                    }
                  }
                },
                "metrics": {
                  "metrics_collected": {
                    "cpu": {
                      "measurement": ["cpu_usage_idle", "cpu_usage_iowait", "cpu_usage_user", "cpu_usage_system"]
                    },
                    "mem": {
                      "measurement": ["mem_used_percent"]
                    },
                    "disk": {
                      "measurement": ["disk_used_percent"],
                      "metrics_collection_interval": 60
                    }
                  }
                }
              }
              EOL

              /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/bin/config.json -s

              # Pull application image
              docker pull ${var.app_image}

              # Run application container
              docker run -d \
                --name district-award-travel-app \
                -p 80:80 \
                -e DB_HOST=${aws_db_instance.award_travel_db.address} \
                -e DB_NAME=${var.db_name} \
                -e DB_USER=${var.db_username} \
                -e DB_PASSWORD=${var.db_password} \
                -e AWS_REGION=${var.aws_region} \
                -v /var/log/app:/var/log/app \
                ${var.app_image}
              EOF
            )

  tag_specifications {
    resource_type = "instance"
    tags = {
      Name        = "district-award-travel-app-server"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }

  tag_specifications {
    resource_type = "volume"
    tags = {
      Name        = "district-award-travel-app-volume"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Auto Scaling Group
resource "aws_autoscaling_group" "app_asg" {
  name                = "district-award-travel-app-asg"
  min_size            = var.min_instances
  max_size            = var.max_instances
  desired_capacity    = var.desired_capacity
  vpc_zone_identifier = module.vpc.public_subnets

  launch_template {
    id      = aws_launch_template.app_launch_template.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "district-award-travel-app-server"
    propagate_at_launch = true
  }

  tag {
    key                 = "Environment"
    value               = var.environment
    propagate_at_launch = true
  }

  tag {
    key                 = "ManagedBy"
    value               = "Terraform"
    propagate_at_launch = true
  }
}

# RDS Database for Award Travel Data
resource "aws_db_subnet_group" "db_subnet_group" {
  name       = "district-award-travel-db-subnet-group"
  subnet_ids = module.vpc.private_subnets

  tags = {
    Name        = "district-award-travel-db-subnet-group"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_db_instance" "award_travel_db" {
  identifier             = "district-award-travel-db"
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  max_allocated_storage  = 100
  storage_type           = "gp2"
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  parameter_group_name   = "default.postgres15"
  skip_final_snapshot    = false
  final_snapshot_identifier = "district-award-travel-db-final-snapshot"
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.db_subnet_group.name
  multi_az               = true
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  publicly_accessible    = false
  storage_encrypted      = true

  tags = {
    Name        = "district-award-travel-db"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# CloudWatch Alarms for Auto Scaling
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "district-award-travel-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EC2 CPU utilization"
  alarm_actions       = [aws_autoscaling_policy.scale_up.arn]

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app_asg.name
  }
}

resource "aws_cloudwatch_metric_alarm" "low_cpu" {
  alarm_name          = "district-award-travel-low-cpu"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "30"
  alarm_description   = "This metric monitors EC2 CPU utilization"
  alarm_actions       = [aws_autoscaling_policy.scale_down.arn]

  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.app_asg.name
  }
}

# Auto Scaling Policies
resource "aws_autoscaling_policy" "scale_up" {
  name                   = "district-award-travel-scale-up"
  scaling_adjustment     = 1
  adjustment_type        = "ChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = aws_autoscaling_group.app_asg.name
}

resource "aws_autoscaling_policy" "scale_down" {
  name                   = "district-award-travel-scale-down"
  scaling_adjustment     = -1
  adjustment_type        = "ChangeInCapacity"
  cooldown               = 300
  autoscaling_group_name = aws_autoscaling_group.app_asg.name
}

# Route 53 Record for Application Load Balancer
resource "aws_lb" "app_alb" {
  name               = "district-award-travel-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.app_sg.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = false

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    enabled = true
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_lb_target_group" "app_tg" {
  name     = "district-award-travel-tg"
  port     = 80
  protocol = "HTTP"
  vpc_id   = module.vpc.vpc_id

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
    matcher             = "200-399"
  }
}

resource "aws_lb_listener" "app_listener" {
  load_balancer_arn = aws_lb.app_alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app_tg.arn
  }
}

# S3 Bucket for ALB Logs
resource "aws_s3_bucket" "alb_logs" {
  bucket = "district-award-travel-alb-logs-${data.aws_caller_identity.current.account_id}"
  acl    = "private"

  versioning {
    enabled = true
  }

  server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# S3 Bucket Policy for ALB Logs
resource "aws_s3_bucket_policy" "alb_logs_policy" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = {
          AWS = "arn:aws:iam::027434742980:root" # AWS ELB account ID for us-east-1
        }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.alb_logs.arn}/*"
      }
    ]
  })
}

# CloudFront Distribution for Global CDN
resource "aws_cloudfront_distribution" "app_cdn" {
  origin {
    domain_name = aws_lb.app_alb.dns_name
    origin_id   = "district-award-travel-alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  comment             = "District Award Travel CDN"
  default_root_object = ""

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "district-award-travel-alb"

    forwarded_values {
      query_string = true
      headers      = ["*"]

      cookies {
        forward = "all"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# CloudWatch Dashboard for Monitoring
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "District-Award-Travel-Monitoring"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric",
        x      = 0,
        y      = 0,
        width  = 12,
        height = 6,
        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", aws_autoscaling_group.app_asg.name],
            [".", "NetworkIn", ".", "."],
            [".", "NetworkOut", ".", "."],
            [".", "DiskReadOps", ".", "."],
            [".", "DiskWriteOps", ".", "."]
          ],
          period = 300,
          stat   = "Average",
          region = var.aws_region,
          title  = "EC2 Instance Metrics"
        }
      },
      {
        type   = "metric",
        x      = 12,
        y      = 0,
        width  = 12,
        height = 6,
        properties = {
          metrics = [
            ["AWS/RDS", "CPUUtilization", "DBInstanceIdentifier", aws_db_instance.award_travel_db.identifier],
            [".", "DatabaseConnections", ".", "."],
            [".", "FreeStorageSpace", ".", "."],
            [".", "ReadLatency", ".", "."],
            [".", "WriteLatency", ".", "."]
          ],
          period = 300,
          stat   = "Average",
          region = var.aws_region,
          title  = "RDS Database Metrics"
        }
      },
      {
        type   = "metric",
        x      = 0,
        y      = 6,
        width  = 12,
        height = 6,
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.app_alb.arn_suffix],
            [".", "HTTPCode_Target_5XX_Count", ".", "."],
            [".", "HTTPCode_Target_4XX_Count", ".", "."],
            [".", "HTTPCode_Target_2XX_Count", ".", "."]
          ],
          period = 300,
          stat   = "Sum",
          region = var.aws_region,
          title  = "ALB Metrics"
        }
      },
      {
        type   = "metric",
        x      = 12,
        y      = 6,
        width  = 12,
        height = 6,
        properties = {
          metrics = [
            ["AWS/AutoScaling", "GroupDesiredCapacity", "AutoScalingGroupName", aws_autoscaling_group.app_asg.name],
            [".", "GroupInServiceInstances", ".", "."],
            [".", "GroupPendingInstances", ".", "."],
            [".", "GroupStandbyInstances", ".", "."]
          ],
          period = 300,
          stat   = "Average",
          region = var.aws_region,
          title  = "Auto Scaling Metrics"
        }
      }
    ]
  })
}

data "aws_caller_identity" "current" {}
