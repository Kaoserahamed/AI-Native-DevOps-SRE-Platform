"""Fast-tier policy checks for the Terraform configuration.

These tests read the `.tf` sources, not a rendered plan: they run in the fast
tier, need no Terraform binary, no cloud credentials and no network access, and
they fail when the infrastructure layout regresses. Schema, provider and lockfile
validation is a different job that runs in the `terraform.yml` workflow.
"""
