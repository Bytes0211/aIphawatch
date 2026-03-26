variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production)."
  type        = string
}

variable "frontend_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 frontend bucket."
  type        = string
}

variable "cloudfront_oai_path" {
  description = "CloudFront Origin Access Identity path for S3 origin config."
  type        = string
}

variable "acm_certificate_arn" {
  description = "ARN of the ACM certificate for HTTPS. Empty string for CloudFront default cert."
  type        = string
  default     = ""
}

variable "domain_aliases" {
  description = "Custom domain aliases for the distribution."
  type        = list(string)
  default     = []
}

variable "price_class" {
  description = "CloudFront price class."
  type        = string
  default     = "PriceClass_100" # US, Canada, Europe
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}
