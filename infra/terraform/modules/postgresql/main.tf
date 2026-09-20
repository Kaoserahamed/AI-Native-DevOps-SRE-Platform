# PostgreSQL RDS instance for the platform.

# Secrets Manager entry for the database credentials.
resource "aws_secretsmanager_secret" "this" {
  name                    = "ai-native-devops-sre-${var.environment}-postgresql"
  description             = "PostgreSQL credentials for the ${var.environment} environment"
  recovery_window_in_days = var.environment == "production" ? 30 : 0
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-postgresql-secret"
  })
}

resource "aws_secretsmanager_secret_version" "this" {
  secret_id = aws_secretsmanager_secret.this.id
  secret_string = jsonencode({
    username = var.db_username
    password = var.db_password
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = var.db_name
  })
}

# DB subnet group.
resource "aws_db_subnet_group" "this" {
  name       = "ai-native-devops-sre-${var.environment}-db-subnet-group"
  subnet_ids = var.db_subnet_group_subnet_ids
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-db-subnet-group"
  })
}

# Parameter group with logging enabled.
resource "aws_db_parameter_group" "this" {
  name   = "ai-native-devops-sre-${var.environment}-param-group"
  family = "postgres15"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-param-group"
  })
}

# RDS instance.
resource "aws_db_instance" "this" {
  allocated_storage            = var.storage_gb
  max_allocated_storage        = var.max_allocated_storage_gb
  storage_type                 = "gp3"
  engine                       = "postgres"
  engine_version               = "15"
  db_name                      = var.db_name
  username                     = var.db_username
  password                     = var.db_password
  parameter_group_name         = aws_db_parameter_group.this.name
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = var.vpc_security_group_ids
  instance_class               = var.instance_class
  skip_final_snapshot          = var.environment != "production"
  final_snapshot_identifier   = var.environment == "production" ? null : "ai-native-devops-sre-${var.environment}-final"
  deletion_protection          = var.deletion_protection
  backup_retention_period      = var.backup_retention_days
  multi_az                     = var.environment == "production"
  publicly_accessible          = false
  storage_encrypted            = true
  kms_key_id                   = var.environment == "production" ? aws_kms_key.postgresql.arn : null
  enable_cloudwatch_logs_exports = var.enabled_cloudwatch_logs_exports
  copy_tags_to_snapshot        = true

  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-postgresql"
  })
}

# KMS key for production encryption.
resource "aws_kms_key" "postgresql" {
  count         = var.environment == "production" ? 1 : 0
  description   = "KMS key for PostgreSQL RDS instance in ${var.environment}"
  enable_key_rotation = true
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-postgresql-kms"
  })
}

resource "aws_kms_alias" "postgresql" {
  count         = var.environment == "production" ? 1 : 0
  name          = "alias/ai-native-devops-sre-${var.environment}-postgresql"
  target_key_id = aws_kms_key.postgresql[0].key_id
}