# Redis module variables.

variable "environment" {
  description = "The deployment environment."
  type        = string
}

variable "aws_region" {
  description = "The AWS region."
  type        = string
}

variable "redis_cluster_name" {
  description = "The name of the ElastiCache cluster."
  type        = string
}

variable "vpc_security_group_ids" {
  description = "Security group IDs to attach to the Redis cluster."
  type        = list(string)
}

variable "subnet_ids" {
  description = "Subnet IDs for the cache subnet group."
  type        = list(string)
}

variable "common_tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
}

variable "node_type" {
  description = "The node type for the Redis cluster."
  type        = string
  default     = "cache.t3.micro"
}

variable "num_cache_nodes" {
  description = "The number of cache nodes."
  type        = number
  default     = 1
}

variable "engine_version" {
  description = "The Redis engine version."
  type        = string
  default     = "7.2"
}

variable "parameter_group_family" {
  description = "The parameter group family."
  type        = string
  default     = "redis7"
}

variable "at_rest_encryption_enabled" {
  description = "Whether to enable encryption at rest."
  type        = bool
  default     = true
}

variable "transit_encryption_enabled" {
  description = "Whether to enable encryption in transit."
  type        = bool
  default     = true
}

variable "auth_token" {
  description = "The AUTH token (optional)."
  type        = string
  default     = ""
  sensitive   = true
}

variable "automatic_failure_detection_enabled" {
  description = "Whether to enable automatic cluster failure detection."
  type        = bool
  default     = true
}