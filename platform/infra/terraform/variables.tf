# Variables for District Award Travel Infrastructure
# Managed by Mitchell Hashimoto - Infrastructure Engineer

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "private_subnets" {
  description = "List of private subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnets" {
  description = "List of public subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "admin_cidr_blocks" {
  description = "CIDR blocks for admin access"
  type        = list(string)
  default     = ["0.0.0.0/0"] # In production, restrict this!
}

variable "ami_id" {
  description = "AMI ID for EC2 instances"
  type        = string
  default     = "ami-0c55b159cbfafe1f0" # Ubuntu 22.04 LTS in us-east-1
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
  default     = "district-award-travel-key"
}

variable "min_instances" {
  description = "Minimum number of instances in ASG"
  type        = number
  default     = 2
}

variable "max_instances" {
  description = "Maximum number of instances in ASG"
  type        = number
  default     = 10
}

variable "desired_capacity" {
  description = "Desired number of instances in ASG"
  type        = number
  default     = 3
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "awardtravel"
}

variable "db_username" {
  description = "Database username"
  type        = string
  default     = "awardadmin"
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  default     = "SecurePassword123!" # In production, use secrets management!
  sensitive   = true
}

variable "app_image" {
  description = "Docker image for the application"
  type        = string
  default     = "district-award-travel/app:latest"
}
