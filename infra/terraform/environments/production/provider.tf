# Provider configuration for production environment.

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# Production environment should be deployed to a separate AWS account with
# stricter access controls. See docs/13-terraform.md for the account separation
# strategy and the runbook in docs/20-runbooks/ for operational procedures.