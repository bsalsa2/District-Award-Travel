variable "aws_region" {
  type        = string
  default     = "us-west-2"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  type        = string
  default     = "10.0.1.0/24"
}

variable "instance_type" {
  type        = string
  default     = "t2.micro"
}

variable "db_instance_class" {
  type        = string
  default     = "db.t2.micro"
}

variable "db_engine" {
  type        = string
  default     = "postgres"
}

variable "db_engine_version" {
  type        = string
  default     = "13.4"
}

variable "db_username" {
  type        = string
  default     = "awardtraveluser"
}

variable "db_password" {
  type        = string
  default     = "awardtravelpassword"
}
