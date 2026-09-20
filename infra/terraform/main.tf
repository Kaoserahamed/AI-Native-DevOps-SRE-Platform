# AI-Native DevOps & SRE Platform — Terraform infrastructure.
#
# Covers the cloud-side dependencies the platform needs: a Kubernetes cluster, PostgreSQL, Redis,
# container registry, networking, and monitoring. Everything is modelled as reusable modules so that
# each environment (dev/staging/production) is a thin consumer rather than a copy of the others.
#
# Provider and module versions are pinned explicitly; the lockfile is committed (Task 4.3). See
# docs/13-terraform.md for the full strategy, and ADR-0004/0005/0006 for the storage and registry
# choices this references.

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Backend selection is an environment concern: each environment configures its own state bucket and
  # DynamoDB lock table. The root module does not know which one — that is set by the environment
  # wrapper (environments/<name>/main.tf) or by an explicit -backend-config at init time. This keeps
  # `terraform init -backend=false` usable for static validation in CI (Task 16.4).
  #
  # Uncomment and fill in for a concrete run:
  #   backend "s3" {
  #     bucket         = "ai-native-devops-sre-tf-state"
  #     key            = "production/terraform.tfstate"
  #     region         = "us-east-1"
  #     dynamodb_table = "ai-native-devops-sre-tf-locks"
  #     encrypt        = true
  #   }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Platform  = "ai-native-devops-sre"
      ManagedBy = "terraform"
      Project   = "ai-native-devops-sre"
    }
  }
}

locals {
  common_tags = {
    Environment = var.environment
    Name        = "ai-native-devops-sre-${var.environment}"
  }
}

resource "random_id" "platform" {
  byte_length = 3
}

module "networking" {
  source = "./modules/networking"

  environment         = var.environment
  aws_region          = var.aws_region
  vpc_cidr            = var.vpc_cidr
  availability_zones  = var.availability_zones
  enable_nat_gateways = var.enable_nat_gateways
  common_tags         = local.common_tags
  platform_id         = random_id.platform.hex
}

module "kubernetes" {
  source = "./modules/kubernetes"

  environment         = var.environment
  aws_region          = var.aws_region
  vpc_id              = module.networking.vpc_id
  private_subnet_ids  = module.networking.private_subnet_ids
  public_subnet_ids   = module.networking.public_subnet_ids
  cluster_name        = "ai-native-devops-sre-${var.environment}"
  cluster_version     = var.kubernetes_version
  node_instance_types = var.kubernetes_node_instance_types
  desired_size        = var.kubernetes_desired_size
  min_size            = var.kubernetes_min_size
  max_size            = var.kubernetes_max_size
  common_tags         = local.common_tags
  platform_id         = random_id.platform.hex
}

module "postgresql" {
  source = "./modules/postgresql"

  environment            = var.environment
  aws_region             = var.aws_region
  vpc_id                 = module.networking.vpc_id
  subnet_ids             = module.networking.private_subnet_ids
  instance_class         = var.postgresql_instance_class
  engine_version         = var.postgresql_engine_version
  allocated_storage      = var.postgresql_allocated_storage
  max_allocated_storage  = var.postgresql_max_allocated_storage
  username               = var.postgresql_username
  common_tags            = local.common_tags
  platform_id            = random_id.platform.hex
  kms_key_arn            = var.postgresql_kms_key_arn
}

module "redis" {
  source = "./modules/redis"

  environment       = var.environment
  aws_region        = var.aws_region
  vpc_id            = module.networking.vpc_id
  subnet_ids        = module.networking.private_subnet_ids
  node_type         = var.redis_node_type
  engine_version    = var.redis_engine_version
  common_tags       = local.common_tags
  platform_id       = random_id.platform.hex
  kms_key_arn       = var.redis_kms_key_arn
}
output "vpc_id" {
  description = "The VPC that hosts the platform."
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs for data stores and cluster nodes."
  value       = module.networking.private_subnet_ids
}

output "cluster_name" {
  description = "The Kubernetes cluster name."
  value       = module.kubernetes.cluster_name
}

output "cluster_endpoint" {
  description = "The Kubernetes cluster endpoint."
  value       = module.kubernetes.cluster_endpoint
  sensitive   = true
}

output "cluster_certificate_authority_data" {
  description = "The cluster certificate authority data."
  value       = module.kubernetes.cluster_certificate_authority_data
  sensitive   = true
}

output "postgresql_endpoint" {
  description = "The PostgreSQL instance endpoint."
  value       = module.postgresql.endpoint
}

output "postgresql_port" {
  description = "The PostgreSQL instance port."
  value       = module.postgresql.port
}

output "postgresql_instance_id" {
  description = "The PostgreSQL instance identifier."
  value       = module.postgresql.instance_id
}

output "redis_endpoint" {
  description = "The Redis endpoint."
  value       = module.redis.endpoint
}

output "redis_port" {
  description = "The Redis port."
  value       = module.redis.port
}

output "redis_resource_id" {
  description = "The Redis replication group resource identifier."
  value       = module.redis.replication_group_id
}

output "container_registry_repository_url" {
  description = "The container registry repository URL."
  value       = module.container_registry.repository_url
}

output "platform_id" {
  description = "A stable random identifier for the platform."
  value       = random_id.platform.hex
}

output "managed_prometheus_workspace_id" {
  description = "The managed Prometheus workspace ID, when created."
  value       = module.monitoring.workspace_id
  sensitive   = true
}

module "container_registry" {
  source = "./modules/container-registry"

  environment           = var.environment
  aws_region            = var.aws_region
  repository_name       = "ai-native-devops-sre-${var.environment}"
  image_tag_mutability = var.container_registry_image_tag_mutability
  common_tags           = local.common_tags
}

module "monitoring" {
  source = "./modules/monitoring"

  environment       = var.environment
  aws_region        = var.aws_region
  common_tags       = local.common_tags
  create_workspace  = var.create_managed_prometheus
}