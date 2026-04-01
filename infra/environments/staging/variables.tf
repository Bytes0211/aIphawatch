variable "project" {
  description = "Project name."
  type        = string
  default     = "alphawatch"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "staging"
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "rds_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t3.medium"
}

variable "redis_node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.t3.micro"
}

variable "api_image" {
  description = "Docker image for the API container."
  type        = string
  default     = "nginx:latest"
}

variable "worker_image" {
  description = "Docker image for the worker container."
  type        = string
  default     = "nginx:latest"
}

variable "acm_certificate_arn" {
  description = "ARN of ACM certificate for HTTPS. Leave empty for HTTP-only staging."
  type        = string
  default     = ""
}

variable "migration_drill_github_connection_arn" {
  description = "CodeConnections ARN used by the staging migration drill CodeBuild project."
  type        = string
  default     = ""
}

variable "migration_drill_repository_url" {
  description = "Repository URL CodeBuild should clone for the migration drill."
  type        = string
  default     = "https://github.com/Bytes0211/aIphawatch.git"
}

variable "migration_drill_source_version" {
  description = "Git ref used by the migration drill CodeBuild project."
  type        = string
  default     = "main"
}
