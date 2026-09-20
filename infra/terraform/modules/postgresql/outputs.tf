# Outputs from the PostgreSQL module.

output "endpoint" {
  description = "The connection endpoint."
  value       = aws_db_instance.this.endpoint
}

output "port" {
  description = "The port."
  value       = aws_db_instance.this.port
}

output "database_name" {
  description = "The database name."
  value       = aws_db_instance.this.db_name
}

output "secret_arn" {
  description = "The ARN of the secrets manager secret."
  value       = aws_secretsmanager_secret.this.arn
}

output "instance_id" {
  description = "The RDS instance identifier."
  value       = aws_db_instance.this.id
}

output "arn" {
  description = "The ARN of the RDS instance."
  value       = aws_db_instance.this.arn
}