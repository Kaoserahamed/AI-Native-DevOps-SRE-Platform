# NAT gateways and Elastic IPs for private subnet internet access.

resource "aws_eip" "this" {
  count  = var.enable_nat_gateways ? length(var.availability_zones) : 0
  domain = "vpc"
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-eip"
  })
}

resource "aws_nat_gateway" "this" {
  count         = var.enable_nat_gateways ? length(var.availability_zones) : 0
  allocation_id = aws_eip.this[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-nat"
  })
  depends_on = [aws_internet_gateway.this]
}