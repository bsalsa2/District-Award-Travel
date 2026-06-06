# Configure the AWS Provider
provider "aws" {
  region = "us-west-2"
}

# Create a VPC
resource "aws_vpc" "award_travel_vpc" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "Award Travel VPC"
  }
}

# Create a subnet
resource "aws_subnet" "award_travel_subnet" {
  vpc_id            = aws_vpc.award_travel_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-west-2a"
  tags = {
    Name = "Award Travel Subnet"
  }
}

# Create a security group
resource "aws_security_group" "award_travel_sg" {
  name        = "award_travel_sg"
  description = "Allow inbound traffic on port 80 and 22"
  vpc_id      = aws_vpc.award_travel_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "Award Travel Security Group"
  }
}

# Create an EC2 instance
resource "aws_instance" "award_travel_instance" {
  ami           = "ami-0c94855ba95c71c99"
  instance_type = "t2.micro"
  vpc_security_group_ids = [aws_security_group.award_travel_sg.id]
  subnet_id = aws_subnet.award_travel_subnet.id
  key_name               = "award_travel_key"
  tags = {
    Name = "Award Travel Instance"
  }
}

# Create a database instance
resource "aws_db_instance" "award_travel_db" {
  allocated_storage    = 20
  engine               = "postgres"
  engine_version       = "13.4"
  instance_class       = "db.t2.micro"
  name                 = "awardtravel"
  username             = "awardtraveluser"
  password             = "awardtravelpassword"
  vpc_security_group_ids = [aws_security_group.award_travel_sg.id]
  db_subnet_group_name = aws_db_subnet_group.award_travel_db_subnet_group.name
  tags = {
    Name = "Award Travel Database"
  }
}

# Create a database subnet group
resource "aws_db_subnet_group" "award_travel_db_subnet_group" {
  name       = "award_travel_db_subnet_group"
  subnet_ids = [aws_subnet.award_travel_subnet.id]

  tags = {
    Name = "Award Travel Database Subnet Group"
  }
}
