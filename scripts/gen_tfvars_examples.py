import os

prod = """# Production environment variables.
# Copy to terraform.tfvars and fill in secrets before running.

environment = "production"

# aws_region and vpc_cidr are usually pinned per environment and not overridden.

postgresql_username = "ai_native_admin"
# postgresql_password is set via AWS Secrets Manager, not in this file.

# PostgreSQL deletion protection is enabled in production.
postgresql_deletion_protection = true

# Redis AUTH token is set via AWS Secrets Manager.
# redis_auth_token is not placed here.

# Container registry uses immutable tags in production.
container_registry_image_tag_mutability = "IMMUTABLE"

# Managed Prometheus workspace is created for production observability.
create_managed_prometheus = true
"""

with open("infra/terraform/environments/production/terraform.tfvars.example", "w") as f:
    f.write(prod)

staging = """# Staging environment variables.
# Copy to terraform.tfvars and adjust before running.

environment = "staging"

postgresql_username = "ai_native_admin"

# Staging uses mutable tags to speed up iteration.
container_registry_image_tag_mutability = "MUTABLE"

# Managed Prometheus workspace is created for staging observability.
create_managed_prometheus = true
"""

with open("infra/terraform/environments/staging/terraform.tfvars.example", "w") as f:
    f.write(staging)

dev = """# Development environment variables.
# Copy to terraform.tfvars and adjust before running.
# Secrets are not committed; configure them via AWS Secrets Manager or
# environment variables when running locally with Terraform.

environment = "dev"

postgresql_username = "ai_native_admin"

# NAT gateways are disabled in dev to reduce cost when the VPC does not
# need outbound internet from private subnets.
enable_nat_gateways = false

# Dev uses smaller instance types and fewer nodes.
kubernetes_node_instance_types = ["t3.small"]
kubernetes_desired_size = 1
kubernetes_min_size = 1
kubernetes_max_size = 2

# Dev PostgreSQL is the smallest practical instance.
postgresql_instance_class = "db.t3.micro"
postgresql_allocated_storage = 10
postgresql_max_allocated_storage = 20

# Dev Redis is the smallest practical node.
redis_node_type = "cache.t3.micro"

# Mutable tags in dev so iterative rebuilds are cheap.
container_registry_image_tag_mutability = "MUTABLE"

# Managed Prometheus workspace is created for dev observability.
create_managed_prometheus = true
"""

with open("infra/terraform/environments/dev/terraform.tfvars.example", "w") as f:
    f.write(dev)

print("Created terraform.tfvars.example files for dev, staging, production")
