# Monitoring module outputs.

output "workspace_id" {
  description = "The ID of the AMP workspace, when created."
  value       = try(aws_prometheus_workspace.this[0].id, null)
  sensitive   = true
}

output "workspace_arn" {
  description = "The ARN of the AMP workspace, when created."
  value       = try(aws_prometheus_workspace.this[0].arn, null)
  sensitive   = true
}