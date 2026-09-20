# Container registry variable descriptions.

variable "environment" {
  description = "The deployment environment. Passed through so the module can tag resources consistently with the rest of the platform."
  type        = string
}

variable "aws_region" {
  description = "The AWS region that hosts the registry."
  type        = string
}

variable "repository_name" {
  description = "Human-readable name for the ECR repository. The environment-specific URL is derived from this value."
  type        = string
}

variable "image_tag_mutability" {
  description = "Whether tags in this repository may be overwritten. IMMUTABLE is recommended for production so manifests can pin an image by its digest."
  type        = string
  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "image_tag_mutability must be MUTABLE or IMMUTABLE."
  }
}

variable "common_tags" {
  description = "Owning tags applied to every resource the module creates."
  type        = map(string)
}
