# Redis ElastiCache cluster for the platform.

# Cache subnet group.
resource "aws_elasticache_subnet_group" "this" {
  name       = "ai-native-devops-sre-${var.environment}-redis-subnet-group"
  subnet_ids = var.subnet_ids
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-redis-subnet-group"
  })
}

# Parameter group.
resource "aws_elasticache_parameter_group" "this" {
  name   = "ai-native-devops-sre-${var.environment}-redis-param-group"
  family = var.parameter_group_family

  # Enable slow log capture for observability.
  parameter {
    name  = "slowlog-log-slower-than"
    value = "10000"
  }

  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-redis-param-group"
  })
}

# Replication group (single node for dev/staging, multi-node for production).
resource "aws_elasticache_replication_group" "this" {
  replication_group_id          = "ai-native-devops-sre-${var.environment}-redis"
  replication_group_description = "Redis cache for ${var.environment} environment"
  engine                        = "redis"
  engine_version                = var.engine_version
  node_type                     = var.node_type
  num_cache_clusters            = var.num_cache_nodes > 1 ? var.num_cache_nodes : null
  num_node_groups               = var.num_cache_nodes > 1 ? 1 : null
  cache_node_count              = var.num_cache_nodes > 1 ? null : var.num_cache_nodes
  parameter_group_name          = aws_elasticache_parameter_group.this.name
  port                          = 6379
  subnet_group_name             = aws_elasticache_subnet_group.this.name
  security_group_ids            = var.vpc_security_group_ids
  at_rest_encryption_enabled    = var.at_rest_encryption_enabled
  transit_encryption_enabled    = var.transit_encryption_enabled
  auth_token                    = var.auth_token != "" ? var.auth_token : null
  automatic_failover_enabled    = var.num_cache_nodes > 1
  automatic_version_upgrade     = true
  snapshot_retention_limit      = var.environment == "production" ? 7 : 0
  snapshot_window               = var.environment == "production" ? "03:00-04:00" : null
  deletion_protection           = var.environment == "production"

  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-redis"
  })
}

# CloudWatch log delivery is configured via the AWS console or separate infrastructure as it
# requires an existing CloudWatch Logs log group. The module outputs the endpoint for connecting.