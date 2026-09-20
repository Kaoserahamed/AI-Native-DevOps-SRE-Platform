# Outputs from the container registry module.

output "repository_url" {
  description = "The URL of the ECR repository used to store application images."
  value       = aws_ecr_repository.this.repository_url
}

output "repository_arn" {
  description = "The ARN of the ECR repository."
  value       = aws_ecr_repository.this.arn
}

output "image_scan_configuration" {
  description = "Whether image scanning is enabled on push."
  value       = aws_ecr_repository.this.image_scanning_configuration[0].scan_on_push
}
