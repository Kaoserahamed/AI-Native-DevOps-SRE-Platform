# Public and private subnets across availability zones.

locals {
  public_subnet_cidrs  = [for i in range(0, length(var.availability_zones)) : cidrsubnet(var.vpc_cidr, 8, i)]
  private_subnet_cidrs = [for i in range(length(var.availability_zones), 2 * length(var.availability_zones)) : cidrsubnet(var.vpc_cidr, 8, i)]
}

resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.this.id
  cidr_block              = local.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-public-${var.availability_zones[count.index]}"
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.this.id
  cidr_block        = local.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  tags = merge(var.common_tags, {
    Name = "ai-native-devops-sre-${var.environment}-private-${var.availability_zones[count.index]}"
  })
}