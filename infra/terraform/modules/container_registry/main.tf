# Container registry module for the platform.

resource "aws_ecr_repository" "this" {
  name                 = var.repository_name
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-ecr"
  })
}

# Retention policy so the registry does not grow without bound.
resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep recently pushed images, retain at most 50, expire older than 90 days"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 50
      }
      action = {
        type = "expire"
      }
    }]
  })
}
