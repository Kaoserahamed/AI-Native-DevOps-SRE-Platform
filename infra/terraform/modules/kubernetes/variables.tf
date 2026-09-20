# Kubernetes module variables.

variable "environment" {
  description = "The deployment environment."
  type        = string
}

variable "aws_region" {
  description = "The AWS region."
  type        = string
}

variable "vpc_id" {
  description = "The VPC ID."
  type        = string
}

variable "private_subnet_ids" {
  description = "The private subnet IDs for the cluster."
  type        = list(string)
}

variable "cluster_security_group_id" {
  description = "The security group ID for the EKS cluster."
  type        = string
}

variable "node_group_security_group_id" {
  description = "The security group ID for the node group."
  type        = string
}

variable "common_tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
}

variable "platform_id" {
  description = "A stable platform identifier used in naming."
  type        = string
}

variable "cluster_name" {
  description = "The name of the EKS cluster."
  type        = string
}

variable "kubernetes_version" {
  description = "The Kubernetes version."
  type        = string
}

variable "node_instance_types" {
  description = "The instance types for the node group."
  type        = list(string)
}

variable "node_min_size" {
  description = "The minimum number of nodes."
  type        = number
}

variable "node_max_size" {
  description = "The maximum number of nodes."
  type        = number
}

variable "node_desired_size" {
  description = "The desired number of nodes."
  type        = number
}