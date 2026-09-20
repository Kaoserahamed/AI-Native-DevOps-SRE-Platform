# Staging environment configuration.

locals {
  common_tags = {
    Environment = var.environment
    Project     = "ai-native-devops-sre"
    ManagedBy   = "terraform"
    Team        = "platform"
  }

  platform_id = "ai-native-devops-sre"
}

module "networking" {
  source = "../../modules/networking"

  environment          = var.environment
  aws_region           = var.aws_region
  vpc_cidr             = var.vpc_cidr
  availability_zones   = var.availability_zones
  enable_nat_gateways  = var.enable_nat_gateways
  common_tags          = local.common_tags
  platform_id          = local.platform_id
}

module "kubernetes" {
  source = "../../modules/kubernetes"

  environment               = var.environment
  aws_region                = var.aws_region
  vpc_id                    = module.networking.vpc_id
  private_subnet_ids        = module.networking.private_subnet_ids
  cluster_security_group_id = module.networking.eks_cluster_security_group_id
  node_group_security_group_id = module.networking.eks_cluster_security_group_id
  common_tags               = local.common_tags
  platform_id               = local.platform_id
  cluster_name              = "${local.platform_id}-${var.environment}-eks"
  kubernetes_version        = var.kubernetes_version
  node_instance_types       = var.node_instance_types
  node_min_size             = var.node_min_size
  node_max_size             = var.node_max_size
  node_desired_size         = var.node_desired_size
}

module "postgresql" {
  source = "../../modules/postgresql"

  environment                      = var.environment
  aws_region                       = var.aws_region
  db_name                          = var.db_name
  db_username                      = var.db_username
  db_password                      = var.db_password
  vpc_security_group_ids           = [module.networking.postgresql_security_group_id]
  db_subnet_group_subnet_ids       = module.networking.private_subnet_ids
  common_tags                      = local.common_tags
  instance_class                   = var.postgres_instance_class
  storage_gb                       = var.postgres_storage_gb
  max_allocated_storage_gb         = var.postgres_max_allocated_storage_gb
  enabled_cloudwatch_logs_exports  = var.enabled_cloudwatch_logs_exports
  deletion_protection              = var.postgres_deletion_protection
  backup_retention_days            = var.postgres_backup_retention_days
}

module "redis" {
  source = "../../modules/redis"

  environment                = var.environment
  aws_region                 = var.aws_region
  redis_cluster_name         = "${local.platform_id}-${var.environment}-redis"
  vpc_security_group_ids     = [module.networking.redis_security_group_id]
  subnet_ids                 = module.networking.private_subnet_ids
  common_tags                = local.common_tags
  node_type                  = var.redis_node_type
  num_cache_nodes            = var.redis_num_cache_nodes
  engine_version             = var.redis_engine_version
  parameter_group_family     = var.redis_parameter_group_family
  at_rest_encryption_enabled = var.redis_at_rest_encryption_enabled
  transit_encryption_enabled = var.redis_transit_encryption_enabled
  auth_token                 = var.redis_auth_token
}

output "vpc_id" {
  description = "The VPC ID."
  value       = module.networking.vpc_id
}

output "vpc_cidr" {
  description = "The VPC CIDR block."
  value       = module.networking.vpc_cidr
}

output "public_subnet_ids" {
  description = "The public subnet IDs."
  value       = module.networking.public_subnet_ids
}

output "private_subnet_ids" {
  description = "The private subnet IDs."
  value       = module.networking.private_subnet_ids
}

output "eks_cluster_name" {
  description = "The EKS cluster name."
  value       = module.kubernetes.cluster_name
}

output "eks_cluster_endpoint" {
  description = "The EKS cluster endpoint."
  value       = module.kubernetes.cluster_endpoint
}

output "eks_cluster_certificate_authority_data" {
  description = "The EKS cluster certificate authority data."
  value       = module.kubernetes.cluster_certificate_authority_data
}

output "postgres_endpoint" {
  description = "The PostgreSQL endpoint."
  value       = module.postgresql.endpoint
}

output "postgres_port" {
  description = "The PostgreSQL port."
  value       = module.postgresql.port
}

output "postgres_database_name" {
  description = "The PostgreSQL database name."
  value       = module.postgresql.database_name
}

output "postgres_secret_arn" {
  description = "The PostgreSQL secret ARN."
  value       = module.postgresql.secret_arn
}

output "redis_endpoint" {
  description = "The Redis endpoint."
  value       = module.redis.endpoint
}

output "redis_port" {
  description = "The Redis port."
  value       = module.redis.port
}