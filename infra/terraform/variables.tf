# Input variables for the Terraform root module.
#
# Every variable has a type, a description, and sensible defaults where possible, so that the
# environment wrappers are as small as possible and the shape of the configuration is self-documenting.
# Variables that must differ between environments are left without defaults and documented in
# docs/13-terraform.md.

variable "environment" {
  description = "The deployment environment. One of dev, staging, or production."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "environment must be dev, staging, or production."
  }
}

variable "aws_region" {
  description = "The AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the platform VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones to spread resources across. Must match the region."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "enable_nat_gateways" {
  description = "Whether to provision NAT gateways for private subnet internet access. Set false for pure-internal environments."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------------------
# Kubernetes
# ---------------------------------------------------------------------------

variable "kubernetes_version" {
  description = "The Kubernetes version for the EKS cluster."
  type        = string
  default     = "1.31"
}

variable "kubernetes_node_instance_types" {
  description = "Instance types for the cluster node groups, in priority order for the capacity-optimized allocation strategy."
  type        = list(string)
  default     = ["t3.medium", "t3.large"]
}

variable "kubernetes_desired_size" {
  description = "Desired number of nodes in the node group."
  type        = number
  default     = 2
}

variable "kubernetes_min_size" {
  description = "Minimum number of nodes in the node group."
  type        = number
  default     = 1
}

variable "kubernetes_max_size" {
  description = "Maximum number of nodes in the node group. The platform treats scaling beyond this as a human decision (Task 9.1)."
  type        = number
  default     = 6
}

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------

variable "postgresql_instance_class" {
  description = "The RDS instance class for PostgreSQL."
  type        = string
  default     = "db.t3.medium"
}

variable "postgresql_engine_version" {
  description = "The PostgreSQL engine version."
  type        = string
  default     = "15.4"
}

variable "postgresql_allocated_storage" {
  description = "Initial storage allocation in GB."
  type        = number
  default     = 20
}

variable "postgresql_max_allocated_storage" {
  description = "Maximum storage for autoscaling in GB. Set 0 to disable."
  type        = number
  default     = 100
}

variable "postgresql_username" {
  description = "The master username for PostgreSQL. The password is stored in AWS Secrets Manager by the module."
  type        = string
  default     = "ai_native_admin"

  sensitive = true
}

variable "postgresql_kms_key_arn" {
  description = "Optional KMS key ARN for encrypting the PostgreSQL instance at rest. Defaults to the AWS-owned key when unset."
  type        = string
  default     = null
}

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

variable "redis_node_type" {
  description = "The ElastiCache node type for Redis."
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_engine_version" {
  description = "The Redis engine version."
  type        = string
  default     = "7.0"
}

variable "redis_kms_key_arn" {
  description = "Optional KMS key ARN for encrypting Redis at rest and in transit. Defaults to the AWS-owned key when unset."
  type        = string
  default     = null
}

# ---------------------------------------------------------------------------
# Container registry
# ---------------------------------------------------------------------------

variable "container_registry_image_tag_mutability" {
  description = "Image tag mutability for the container registry repository. 'MUTABLE' allows overwriting tags; 'IMMUTABLE' forces immutable tags (including SHA-based tags)."
  type        = string
  default     = "MUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.container_registry_image_tag_mutability)
    error_message = "container_registry_image_tag_mutability must be MUTABLE or IMMUTABLE."
  }
}

# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

variable "create_managed_prometheus" {
  description = "Whether to create the Amazon Managed Prometheus workspace. Set false for environments that use an in-cluster Prometheus."
  type        = bool
  default     = true
}