variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production)."
  type        = string
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}
