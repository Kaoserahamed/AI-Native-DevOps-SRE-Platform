# Outputs from the Redis module.

output "endpoint" {
  description = "The primary endpoint for the replication group."
  value       = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "port" {
  description = "The port."
  value       = 6379
}

output "replication_group_id" {
  description = "The replication group ID."
  value       = aws_elasticache_replication_group.this.replication_group_id
}

output "arn" {
  description = "The ARN of the replication group."
  value       = aws_elasticache_replication_group.this.arn
}