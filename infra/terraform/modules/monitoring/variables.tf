# Input variables for the monitoring module.

variable "environment" {
  description = "The deployment environment. Used to name the AMP workspace and tag resources."
  type        = string
}

variable "aws_region" {
  description = "The AWS region that hosts the workspace."
  type        = string
}

variable "common_tags" {
  description = "Owning tags applied to every resource the module creates."
  type        = map(string)
}

variable "create_workspace" {
  description = "Whether to create an Amazon Managed Prometheus workspace. Set false when the environment uses an in-cluster Prometheus instead."
  type        = bool
  default     = true
}

