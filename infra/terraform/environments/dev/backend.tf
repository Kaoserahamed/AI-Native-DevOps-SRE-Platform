# Remote state backend for the dev environment (S3 + DynamoDB, encrypted).
#
# State lives in a versioned, SSE-encrypted (encrypt = true) S3 bucket and
# locking uses a DynamoDB table, so concurrent runs cannot corrupt state and no
# state file is ever committed to git (see docs/13-terraform.md). The dev
# bucket and lock table are separate from the other environments. The
# values below are the conventional defaults; override them at init time with
# `-backend-config` flags without editing this file.

terraform {
  backend "s3" {
    bucket         = "ai-native-devops-sre-tf-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "ai-native-devops-sre-tf-locks-dev"
    encrypt        = true
  }
}
