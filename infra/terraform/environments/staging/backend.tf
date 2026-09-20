# Remote state backend configuration for staging.

terraform {
  backend "s3" {}
  # See docs/13-terraform.md for the backend strategy.
  # The S3 bucket and DynamoDB table are environment-specific (see backend config
  # in terraform.tfvars.example or CI secrets).