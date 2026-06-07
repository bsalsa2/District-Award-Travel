# Outputs for District Award Travel Infrastructure
# Managed by Mitchell Hashimoto - Infrastructure Engineer

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "public_subnets" {
  description = "List of public subnet IDs"
  value       = module.vpc.public_subnets
}

output "private_subnets" {
  description = "List of private subnet IDs"
  value       = module.vpc.private_subnets
}

output "app_security_group_id" {
  description = "Application security group ID"
  value       = aws_security_group.app_sg.id
}

output "db_security_group_id" {
  description = "Database security group ID"
  value       = aws_security_group.db_sg.id
}

output "db_endpoint" {
  description = "RDS database endpoint"
  value       = aws_db_instance.award_travel_db.endpoint
  sensitive   = true
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = aws_lb.app_alb.dns_name
}

output "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.app_cdn.domain_name
}

output "asg_name" {
  description = "Auto Scaling Group name"
  value       = aws_autoscaling_group.app_asg.name
}

output "launch_template_id" {
  description = "Launch template ID"
  value       = aws_launch_template.app_launch_template.id
}

output "cloudwatch_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=District-Award-Travel-Monitoring"
}

output "s3_data_bucket" {
  description = "S3 bucket for award travel data"
  value       = "s3://district-award-travel-data"
}
