variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production)."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the ALB."
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks."
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group ID for the ALB."
  type        = string
}

variable "ecs_api_security_group_id" {
  description = "Security group ID for ECS API tasks."
  type        = string
}

variable "ecs_worker_security_group_id" {
  description = "Security group ID for ECS worker tasks."
  type        = string
}

# Container images
variable "api_image" {
  description = "Docker image for the API container."
  type        = string
  default     = "nginx:latest" # Placeholder until ECR is set up
}

variable "worker_image" {
  description = "Docker image for the worker container."
  type        = string
  default     = "nginx:latest" # Placeholder until ECR is set up
}

# Container resources
variable "api_container_port" {
  description = "Port the API container listens on."
  type        = number
  default     = 8000
}

variable "api_cpu" {
  description = "CPU units for the API task (1024 = 1 vCPU)."
  type        = number
  default     = 2048
}

variable "api_memory" {
  description = "Memory in MB for the API task."
  type        = number
  default     = 4096
}

variable "worker_cpu" {
  description = "CPU units for the worker task."
  type        = number
  default     = 1024
}

variable "worker_memory" {
  description = "Memory in MB for the worker task."
  type        = number
  default     = 2048
}

# Scaling
variable "api_desired_count" {
  description = "Desired number of API tasks."
  type        = number
  default     = 1
}

variable "api_max_count" {
  description = "Maximum number of API tasks."
  type        = number
  default     = 10
}

variable "worker_desired_count" {
  description = "Desired number of worker tasks."
  type        = number
  default     = 1
}

variable "worker_max_count" {
  description = "Maximum number of worker tasks."
  type        = number
  default     = 5
}

# Dependencies
variable "db_host" {
  description = "RDS hostname."
  type        = string
}

variable "db_port" {
  description = "RDS port."
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Database name."
  type        = string
}

variable "db_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for the DB password."
  type        = string
}

variable "redis_host" {
  description = "Redis primary endpoint."
  type        = string
}

variable "redis_port" {
  description = "Redis port."
  type        = number
  default     = 6379
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID."
  type        = string
}

variable "cognito_client_id" {
  description = "Cognito App Client ID."
  type        = string
}

variable "documents_bucket_arn" {
  description = "ARN of the S3 documents bucket."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS. Empty string to skip HTTPS listener."
  type        = string
  default     = ""
}

variable "container_insights" {
  description = "Enable Container Insights on the ECS cluster."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}
