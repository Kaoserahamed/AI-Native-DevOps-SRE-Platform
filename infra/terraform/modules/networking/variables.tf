# Networking module variables.

variable "environment" {
  description = "The deployment environment (dev, staging, production)."
  type        = string
}

variable "aws_region" {
  description = "The AWS region."
  type        = string
}

variable "vpc_cidr" {
  description = "The CIDR block for the VPC."
  type        = string
}

variable "availability_zones" {
  description = "Availability zones to place subnets in."
  type        = list(string)
}

variable "enable_nat_gateways" {
  description = "Whether to create NAT gateways for private subnet internet access."
  type        = bool
  default     = true
}

variable "common_tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
}

variable "platform_id" {
  description = "A stable platform identifier used in naming."
  type        = string
}