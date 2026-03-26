variable "project" {
  description = "Project name used for resource naming."
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production)."
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for the Redis subnet group."
  type        = list(string)
}

variable "security_group_id" {
  description = "Security group ID for the Redis cluster."
  type        = string
}

variable "node_type" {
  description = "ElastiCache node type."
  type        = string
  default     = "cache.t3.micro"
}

variable "purpose" {
  description = "Identifies the primary workload (broker or cache)."
  type        = string
}

variable "maxmemory_policy" {
  description = "maxmemory-policy applied to the parameter group."
  type        = string
}

variable "auth_token" {
  description = "Redis AUTH token for the replication group."
  type        = string
  sensitive   = true
}

variable "num_cache_clusters" {
  description = "Number of cache clusters (nodes) in the replication group."
  type        = number
  default     = 1
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default     = {}
}
