output "vpc_id" {
  value       = aws_vpc.award_travel_vpc.id
}

output "subnet_id" {
  value       = aws_subnet.award_travel_subnet.id
}

output "security_group_id" {
  value       = aws_security_group.award_travel_sg.id
}

output "instance_id" {
  value       = aws_instance.award_travel_instance.id
}

output "db_instance_id" {
  value       = aws_db_instance.award_travel_db.id
}
