output "endpoint" {
  description = "RDS instance endpoint (hostname:port)."
  value       = aws_db_instance.main.endpoint
}

output "address" {
  description = "RDS instance hostname."
  value       = aws_db_instance.main.address
}

output "port" {
  description = "RDS instance port."
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Name of the database."
  value       = aws_db_instance.main.db_name
}

output "db_instance_id" {
  description = "RDS instance identifier."
  value       = aws_db_instance.main.id
}
