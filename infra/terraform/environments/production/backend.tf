# Remote state backend configuration for production.

terraform {
  backend "s3" {}
  # See docs/13-terraform.md for the backend strategy.
  # Production uses separate S3 bucket and DynamoDB table with stricter access controls.
  # Configuration is provided via CI/CD secrets, not committed to the repository.