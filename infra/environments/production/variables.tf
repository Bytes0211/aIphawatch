variable "project" {
  description = "Project name."
  type        = string
  default     = "alphawatch"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.1.0.0/16"
}

variable "rds_instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.r6g.large"
}

variable "redis_node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.r6g.large"
}

variable "api_image" {
  description = "Docker image for the API container."
  type        = string
}

variable "worker_image" {
  description = "Docker image for the worker container."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of ACM certificate for HTTPS. Leave empty for HTTP-only deployment."
  type        = string
  default     = ""
}

variable "domain_aliases" {
  description = "Custom domain aliases for CloudFront."
  type        = list(string)
  default     = []
}
