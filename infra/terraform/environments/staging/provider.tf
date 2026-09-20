# Provider configuration for staging environment.

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# Staging environment can share the same provider configuration but should be
# deployed to a separate AWS account or use separate resource prefixes to avoid
# conflicts with development resources. See docs/13-terraform.md for details.