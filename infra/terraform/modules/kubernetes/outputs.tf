# Outputs from the kubernetes module.

output "cluster_name" {
  description = "The name of the EKS cluster."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "The endpoint for the EKS cluster."
  value       = aws_eks_cluster.this.endpoint
}

output "cluster_certificate_authority_data" {
  description = "The certificate data for the EKS cluster."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_version" {
  description = "The Kubernetes version."
  value       = aws_eks_cluster.this.version
}

output "cluster_security_group_id" {
  description = "The security group ID for the EKS cluster."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "node_group_name" {
  description = "The name of the node group."
  value       = aws_eks_node_group.this.node_group_name
}

output "oidc_provider_arn" {
  description = "The ARN of the OIDC provider."
  value       = aws_iam_openid_connect_provider.this.arn
}