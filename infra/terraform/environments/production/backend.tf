# Remote state backend for the production environment (S3 + DynamoDB, encrypted).
#
# State lives in a versioned, SSE-encrypted (encrypt = true) S3 bucket and
# locking uses a DynamoDB table, so concurrent runs cannot corrupt state and no
# state file is ever committed to git (see docs/13-terraform.md). The production
# bucket and lock table are separate from the other environments. Production additionally restricts backend access to the protected deployment role
# (ideally a separate AWS account). The
# values below are the conventional defaults; override them at init time with
# `-backend-config` flags without editing this file.

terraform {
  backend "s3" {
    bucket         = "ai-native-devops-sre-tf-state-production"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "ai-native-devops-sre-tf-locks-production"
    encrypt        = true
  }
}
