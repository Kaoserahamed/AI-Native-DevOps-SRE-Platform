# Security groups for platform infrastructure.

resource "aws_security_group" "postgresql" {
  name        = "ai-native-devops-sre-${var.environment}-postgresql"
  description = "Allow PostgreSQL access from within the VPC."
  vpc_id      = aws_vpc.this.id
  ingress {
    description = "PostgreSQL from the VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-postgresql-sg"
  })
}

resource "aws_security_group" "redis" {
  name        = "ai-native-devops-sre-${var.environment}-redis"
  description = "Allow Redis access from within the VPC."
  vpc_id      = aws_vpc.this.id
  ingress {
    description = "Redis from the VPC"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-redis-sg"
  })
}

resource "aws_security_group" "eks_cluster" {
  name        = "ai-native-devops-sre-${var.environment}-eks-cluster"
  description = "Allow cluster API access."
  vpc_id      = aws_vpc.this.id
  ingress {
    description = "HTTPS from the VPC"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-eks-cluster-sg"
  })
}