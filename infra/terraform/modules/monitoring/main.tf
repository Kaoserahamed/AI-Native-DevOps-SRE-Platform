# Monitoring module: Amazon Managed Prometheus workspace.

resource "aws_prometheus_workspace" "this" {
  count = var.create_workspace ? 1 : 0

  name = "ai-native-devops-sre-${var.environment}"

  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-amp-workspace"
  })
}