# Production environment variables.

variable "environment" {
  description = "The deployment environment."
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "The AWS region to deploy to."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "The CIDR block for the VPC."
  type        = string
  default     = "10.2.0.0/16"
}

variable "availability_zones" {
  description = "The availability zones to use."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "enable_nat_gateways" {
  description = "Whether to create NAT gateways for private subnets."
  type        = bool
  default     = true
}

variable "kubernetes_version" {
  description = "The Kubernetes version."
  type        = string
  default     = "1.29"
}

variable "node_instance_types" {
  description = "The instance types for EKS nodes."
  type        = list(string)
  default     = ["t3.large", "t3.xlarge"]
}

variable "node_min_size" {
  description = "The minimum number of nodes per node group."
  type        = number
  default     = 3
}

variable "node_max_size" {
  description = "The maximum number of nodes per node group."
  type        = number
  default     = 10
}

variable "node_desired_size" {
  description = "The desired number of nodes per node group."
  type        = number
  default     = 3
}

variable "db_name" {
  description = "The name of the PostgreSQL database."
  type        = string
  default     = "ai_native_devops_sre"
}

variable "db_username" {
  description = "The PostgreSQL master username."
  type        = string
  default     = "admin"
}

variable "db_password" {
  description = "The PostgreSQL master password."
  type        = string
  sensitive   = true
  default     = ""
}

variable "postgres_instance_class" {
  description = "The RDS instance class for PostgreSQL."
  type        = string
  default     = "db.r6g.large"
}

variable "postgres_storage_gb" {
  description = "The allocated storage for PostgreSQL in GB."
  type        = number
  default     = 50
}

variable "postgres_max_allocated_storage_gb" {
  description = "The maximum storage for autoscaling PostgreSQL."
  type        = number
  default     = 500
}

variable "postgres_deletion_protection" {
  description = "Whether to enable deletion protection for PostgreSQL."
  type        = bool
  default     = true
}

variable "postgres_backup_retention_days" {
  description = "Number of days to retain backups."
  type        = number
  default     = 30
}

variable "enabled_cloudwatch_logs_exports" {
  description = "Log types to export to CloudWatch Logs."
  type        = list(string)
  default     = ["postgresql"]
}

variable "redis_node_type" {
  description = "The node type for Redis."
  type        = string
  default     = "cache.r6g.large"
}

variable "redis_num_cache_nodes" {
  description = "The number of Redis cache nodes."
  type        = number
  default     = 2
}

variable "redis_engine_version" {
  description = "The Redis engine version."
  type        = string
  default     = "7.2"
}

variable "redis_parameter_group_family" {
  description = "The Redis parameter group family."
  type        = string
  default     = "redis7"
}

variable "redis_at_rest_encryption_enabled" {
  description = "Whether to enable encryption at rest for Redis."
  type        = bool
  default     = true
}

variable "redis_transit_encryption_enabled" {
  description = "Whether to enable encryption in transit for Redis."
  type        = bool
  default     = true
}

variable "redis_auth_token" {
  description = "The Redis AUTH token."
  type        = string
  sensitive   = true
  default     = ""
}