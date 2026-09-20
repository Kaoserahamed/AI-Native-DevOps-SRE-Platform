# Dev environment Terraform variables.

variable \"environment\" {
  description = \"The deployment environment.\"
  type        = string
  default     = \"dev\"
}

variable \"aws_region\" {
  description = \"The AWS region to deploy the dev environment to.\"
  type        = string
  default     = \"us-east-1\"
}

variable \"vpc_cidr\" {
  description = \"CIDR block for dev VPC.\"
  type        = string
  default     = \"10.0.0.0/16\"
}

variable \"availability_zones\" {
  description = \"Availability zones for dev.\"
  type        = list(string)
  default     = [\"us-east-1a\"]
}

variable \"enable_nat_gateways\" {
  description = \"Whether to enable NAT gateways.\"
  type        = bool
  default     = false
}

# Kubernetes dev values
variable \"kubernetes_version\" {
  description = \"Kubernetes version for EKS.\"
  type        = string
  default     = \"1.28\"
}

variable \"node_instance_types\" {
  description = \"Instance types for dev nodes.\"
  type        = list(string)
  default     = [\"t3.small\"]
}

variable \"node_min_size\" {
  description = \"Minimum node count for dev.\"
  type        = number
  default     = 1
}

variable \"node_max_size\" {
  description = \"Maximum node count for dev.\"
  type        = number
  default     = 3
}

variable \"node_desired_size\" {
  description = \"Desired node count for dev.\"
  type        = number
  default     = 1
}

# PostgreSQL dev values
variable \"db_name\" {
  description = \"Database name.\"
  type        = string
  default     = \"ai_native_sre\"
}

variable \"db_username\" {
  description = \"PostgreSQL master username.\"
  type        = string
  default     = \"admin\"
}

variable \"db_password\" {
  description = \"PostgreSQL master password.\"
  type        = string
  sensitive   = true
  default     = \"\"
}

variable \"postgres_instance_class\" {
  description = \"RDS instance class for dev.\"
  type        = string
  default     = \"db.t3.micro\"
}

variable \"postgres_storage_gb\" {
  description = \"Allocated storage in GB.\"
  type        = number
  default     = 5
}

variable \"postgres_max_allocated_storage_gb\" {
  description = \"Maximum storage for autoscaling.\"
  type        = number
  default     = 20
}

variable \"postgres_deletion_protection\" {
  description = \"Whether to enable deletion protection.\"
  type        = bool
  default     = false
}

variable \"postgres_backup_retention_days\" {
  description = \"Backup retention in days.\"
  type        = number
  default     = 7
}

variable \"enabled_cloudwatch_logs_exports\" {
  description = \"CloudWatch log exports.\"
  type        = list(string)
  default     = [\"postgresql\"]
}

# Redis dev values
variable \"redis_node_type\" {
  description = \"ElastiCache node type.\"
  type        = string
  default     = \"cache.t3.micro\"
}

variable \"redis_num_cache_nodes\" {
  description = \"Number of Redis cache nodes.\"
  type        = number
  default     = 1
}

variable \"redis_engine_version\" {
  description = \"Redis engine version.\"
  type        = string
  default     = \"7.0\"
}

variable \"redis_parameter_group_family\" {
  description = \"Redis parameter group family.\"
  type        = string
  default     = \"redis7\"
}

variable \"redis_at_rest_encryption_enabled\" {
  description = \"Whether to enable at-rest encryption.\"
  type        = bool
  default     = false
}

variable \"redis_transit_encryption_enabled\" {
  description = \"Whether to enable transit encryption.\"
  type        = bool
  default     = false
}

variable \"redis_auth_token\" {
  description = \"Redis AUTH token.\"
  type        = string
  sensitive   = true
  default     = \"\"
}

# Container registry dev values
variable \"container_registry_image_tag_mutability\" {
  description = \"Image tag mutability for ECR.\"
  type        = string
  default     = \"MUTABLE\"
}

# Monitoring dev values
variable \"create_managed_prometheus\" {
  description = \"Whether to create AMP workspace.\"
  type        = bool
  default     = false
}
