# Outputs from the networking module.

output "vpc_id" {
  description = "The VPC ID."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "The VPC CIDR block."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "The public subnet IDs."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "The private subnet IDs."
  value       = aws_subnet.private[*].id
}

output "eks_cluster_security_group_id" {
  description = "The security group ID for the EKS cluster."
  value       = aws_security_group.eks_cluster.id
}

output "postgresql_security_group_id" {
  description = "The security group ID for PostgreSQL."
  value       = aws_security_group.postgresql.id
}

output "redis_security_group_id" {
  description = "The security group ID for Redis."
  value       = aws_security_group.redis.id
}