variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Environment name."
  type        = string
}

variable "aws_region" {
  description = "AWS region for the CodeBuild project."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for VPC-attached builds."
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for the build network interfaces."
  type        = list(string)
}

variable "rds_security_group_id" {
  description = "Security group ID for the target RDS instance."
  type        = string
}

variable "repository_url" {
  description = "Repository URL CodeBuild should clone."
  type        = string
}

variable "github_connection_arn" {
  description = "CodeConnections ARN for GitHub source access."
  type        = string
}

variable "source_version" {
  description = "Default git ref to build."
  type        = string
  default     = "main"
}

variable "buildspec_path" {
  description = "Path to the buildspec file in the repository."
  type        = string
}

variable "db_host" {
  description = "RDS hostname for the migration drill."
  type        = string
}

variable "db_port" {
  description = "RDS port for the migration drill."
  type        = number
}

variable "db_name" {
  description = "Database name for the migration drill."
  type        = string
}

variable "db_user" {
  description = "Database username for the migration drill."
  type        = string
}

variable "db_password_secret_arn" {
  description = "Secrets Manager ARN containing the database password."
  type        = string
}

variable "compute_type" {
  description = "CodeBuild compute type."
  type        = string
  default     = "BUILD_GENERAL1_SMALL"
}

variable "image" {
  description = "Managed image for the CodeBuild environment."
  type        = string
  default     = "aws/codebuild/standard:7.0"
}

variable "build_timeout" {
  description = "Build timeout in minutes."
  type        = number
  default     = 60
}

variable "queued_timeout" {
  description = "Queued timeout in minutes."
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}