# Remote state backend configuration.

terraform {
  # Use S3 + DynamoDB for state storage and locking.
  # See docs/13-terraform.md for the backend strategy and environment separation.
  backend "s3" {}
}