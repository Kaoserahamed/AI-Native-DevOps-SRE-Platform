# Terraform infrastructure

This document describes how Terraform is organised in this repository, where
state lives, which CI gates guard it, and how to run it locally. The design
decision is recorded in [ADR-0009](adr/0009-terraform-environment-separation.md).

## Layout

```text
infra/terraform/
+-- modules/                  # Reusable modules (networking, kubernetes,
|                             # postgresql, redis, container_registry,
|                             # monitoring) with documented inputs/outputs
+-- environments/
|   +-- dev/backend.tf        # Remote state: S3 + DynamoDB (encrypted)
|   +-- staging/backend.tf    # Remote state: S3 + DynamoDB (encrypted)
|   +-- production/backend.tf # Remote state: S3 + DynamoDB (encrypted)
+-- tests/                    # Static configuration tests (no cloud access)
+-- main.tf                   # Root module (validates module composition)
+-- variables.tf
+-- versions.tf               # Pinned Terraform + provider constraints
+-- .terraform.lock.hcl       # Committed provider lockfile (reproducible plans)
```

Each environment root under `environments/` is a thin consumer of the shared
modules: it sets its own variable values and its own remote-state backend, so
a mistake in one environment cannot affect another. Terraform workspaces are
deliberately not used for environment separation.

## Remote state (S3 + DynamoDB, encrypted)

State never lives on a developer machine and is never committed to git
(`scripts/check_repo_policy.py` fails the build on any tracked `*.tfstate`).
Every environment points at its own versioned, server-side-encrypted S3
bucket with a DynamoDB table for state locking:

| Environment | S3 bucket | State key | DynamoDB lock table |
| --- | --- | --- | --- |
| `dev` | `ai-native-devops-sre-tf-state-dev` | `dev/terraform.tfstate` | `ai-native-devops-sre-tf-locks-dev` |
| `staging` | `ai-native-devops-sre-tf-state-staging` | `staging/terraform.tfstate` | `ai-native-devops-sre-tf-locks-staging` |
| `production` | `ai-native-devops-sre-tf-state-production` | `production/terraform.tfstate` | `ai-native-devops-sre-tf-locks-production` |

Each `environments/<name>/backend.tf` declares this with `encrypt = true`:

```hcl
terraform {
  backend "s3" {
    bucket         = "ai-native-devops-sre-tf-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "ai-native-devops-sre-tf-locks-dev"
    encrypt        = true
  }
}
```

Production additionally restricts backend access to the protected deployment
role (ideally a separate AWS account with stricter access controls).

The values in `backend.tf` are the conventional defaults. Override them at
`init` time without editing the file when a deployment needs different
coordinates (for example a bootstrapped bucket name):

```bash
cd infra/terraform/environments/dev
terraform init \
  -backend-config="bucket=my-state-bucket" \
  -backend-config="dynamodb_table=my-lock-table"
```

A Terraform Cloud remote backend (`backend "remote"`) is an acceptable
alternative if the team standardises on it: keep one workspace per
environment, enable remote state encryption, and document the workspace names
here in the same change.

## CI gates (`.github/workflows/infrastructure.yml`)

The `terraform-validate` job runs on every pull request and every push to
`main`. It iterates over each root under `infra/terraform/environments/`:

| Gate | Command / action | Fails the build when ... |
| --- | --- | --- |
| Format | `terraform fmt -check -recursive` per environment root | any file is unformatted |
| Init | `terraform init -backend=false` per environment root | providers/modules do not resolve |
| Validate | `terraform validate` per environment root | the configuration is invalid |
| Plan | `terraform plan -input=false` on pull requests, non-production only | the plan errors (production is intentionally never planned on PRs) |
| Checkov | `bridgecrewio/checkov-action` with `soft_fail: false` | any policy finding (results uploaded as SARIF) |
| tfsec | `aquasecurity/tfsec-action` with `--minimum-severity HIGH` and no `soft_fail` | any HIGH or CRITICAL finding |
| Trivy | `aquasecurity/trivy-action` config scan, `exit-code: 1`, `HIGH,CRITICAL` | any HIGH or CRITICAL misconfiguration (results uploaded as SARIF) |

The job requests `security-events: write` so the SARIF uploads succeed, and
`pull-requests: write` so the non-production plan summary can be posted as a
PR comment. `terraform apply` never runs in CI: apply happens only from a
protected branch or an approved environment, and production apply requires
the production approval gate (see
[ADR-0009](adr/0009-terraform-environment-separation.md) and
[governance](18-governance.md)).

## Local usage

```bash
# Static validation only (no credentials needed, same as CI):
terraform fmt -check -recursive infra/terraform/environments/dev
cd infra/terraform/environments/dev
terraform init -backend=false
terraform validate

# A real plan needs AWS credentials and backend access; state stays remote:
terraform init   # uses environments/dev/backend.tf, nothing is written to git
terraform plan -input=false
```

Copy `terraform.tfvars.example` to `terraform.tfvars` for local variable
values. Secrets (`db_password`, `redis_auth_token`) are never committed: pass
them via AWS Secrets Manager, environment variables, or CI secrets. A static
test (`infra/terraform/tests/test_terraform_config.py`) fails the build if a
`.tf` file contains a literal credential.

## Versions and lockfile

`versions.tf` pins `required_version` and `required_providers`; the resolved
provider hashes are committed in `.terraform.lock.hcl`. Refresh providers
deliberately with `terraform init -upgrade` inside the affected root and
commit the lockfile diff in the same change (see the upgrade procedure in
[governance](18-governance.md)).

## Disaster recovery

State can contain sensitive values, so the backend must be encrypted and
access-controlled (see above). A restore/recovery drill for the state backend
(versioned bucket restore, lock-table rebuild, state re-attachment) is tracked
with the disaster-recovery documentation once it lands; until then, bucket
versioning plus the DynamoDB table are the minimum durability story.

