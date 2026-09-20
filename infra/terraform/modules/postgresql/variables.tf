# PostgreSQL module variables.

variable "environment" {
  description = "The deployment environment."
  type        = string
}

variable "aws_region" {
  description = "The AWS region."
  type        = string
}

variable "db_name" {
  description = "The name of the database."
  type        = string
}

variable "db_username" {
  description = "The master username."
  type        = string
}

variable "db_password" {
  description = "The master password (stored in AWS Secrets Manager)."
  type        = string
  sensitive   = true
}

variable "vpc_security_group_ids" {
  description = "Security group IDs to attach to the RDS instance."
  type        = list(string)
}

variable "db_subnet_group_subnet_ids" {
  description = "Subnet IDs for the DB subnet group."
  type        = list(string)
}

variable "common_tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
}

variable "instance_class" {
  description = "The RDS instance class."
  type        = string
  default     = "db.t3.micro"
}

variable "storage_gb" {
  description = "The allocated storage in GB."
  type        = number
  default     = 20
}

variable "max_allocated_storage_gb" {
  description = "The maximum storage for autoscaling."
  type        = number
  default     = 100
}

variable "enabled_cloudwatch_logs_exports" {
  description = "Log types to export to CloudWatch."
  type        = list(string)
  default     = ["postgresql"]
}

variable "deletion_protection" {
  description = "Whether to enable deletion protection."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Number of days to retain backups."
  type        = number
  default     = 7
}