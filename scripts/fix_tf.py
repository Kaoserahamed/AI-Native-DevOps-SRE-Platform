#!/usr/bin/env python3
"""Generate remaining Terraform files."""
import pathlib

# Write monitoring/variables.tf
pathlib.Path("infra/terraform/modules/monitoring/variables.tf").write_text("""\
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
""")

# Write monitoring/versions.tf
pathlib.Path("infra/terraform/modules/monitoring/versions.tf").write_text("""\
# Monitoring module variable constraints.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}
""")

print("done")
