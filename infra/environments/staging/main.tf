###############################################################################
# AIphaWatch — Staging Environment
# Wires all infrastructure modules together for staging deployment.
###############################################################################

locals {
  tags = {
    Project     = var.project
    Environment = var.environment
  }
}

# -----------------------------------------------------------------------------
# Secrets (must be created first — RDS depends on the generated password)
# -----------------------------------------------------------------------------
module "secrets" {
  source = "../../modules/secrets"

  project     = var.project
  environment = var.environment
  tags        = local.tags
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------
module "vpc" {
  source = "../../modules/vpc"

  project            = var.project
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  az_count           = 2
  single_nat_gateway = true
  tags               = local.tags
}

# -----------------------------------------------------------------------------
# CloudFront OAI (created first to break circular dependency)
# -----------------------------------------------------------------------------
resource "aws_cloudfront_origin_access_identity" "frontend" {
  comment = "${var.project}-${var.environment} frontend OAI"
}

# -----------------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------------
module "s3" {
  source = "../../modules/s3"

  project            = var.project
  environment        = var.environment
  cloudfront_oai_arn = aws_cloudfront_origin_access_identity.frontend.iam_arn
  tags               = local.tags
}

# -----------------------------------------------------------------------------
# CloudFront
# -----------------------------------------------------------------------------
module "cloudfront" {
  source = "../../modules/cloudfront"

  project                              = var.project
  environment                          = var.environment
  frontend_bucket_regional_domain_name = module.s3.frontend_bucket_regional_domain_name
  cloudfront_oai_path                  = aws_cloudfront_origin_access_identity.frontend.cloudfront_access_identity_path
  acm_certificate_arn                  = var.acm_certificate_arn
  price_class                          = "PriceClass_100"
  tags                                 = local.tags
}

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
module "rds" {
  source = "../../modules/rds"

  project             = var.project
  environment         = var.environment
  private_subnet_ids  = module.vpc.private_subnet_ids
  security_group_id   = module.vpc.rds_security_group_id
  instance_class      = var.rds_instance_class
  db_password         = module.secrets.db_password
  multi_az            = false
  allocated_storage   = 20
  deletion_protection = false
  tags                = local.tags
}

# -----------------------------------------------------------------------------
# Broker Redis (Celery)
# -----------------------------------------------------------------------------
module "elasticache_broker" {
  source = "../../modules/elasticache"

  project            = var.project
  environment        = var.environment
  purpose            = "broker"
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_id  = module.vpc.redis_security_group_id
  node_type          = var.redis_node_type
  maxmemory_policy   = "noeviction"
  auth_token         = module.secrets.redis_auth_token
  num_cache_clusters = 1
  tags               = local.tags
}

# -----------------------------------------------------------------------------
# Cache Redis (sessions / chunk cache)
# -----------------------------------------------------------------------------
module "elasticache_cache" {
  source = "../../modules/elasticache"

  project            = var.project
  environment        = var.environment
  purpose            = "cache"
  private_subnet_ids = module.vpc.private_subnet_ids
  security_group_id  = module.vpc.redis_security_group_id
  node_type          = var.redis_node_type
  maxmemory_policy   = "allkeys-lru"
  auth_token         = module.secrets.redis_auth_token
  num_cache_clusters = 1
  tags               = local.tags
}

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
module "cognito" {
  source = "../../modules/cognito"

  project           = var.project
  environment       = var.environment
  mfa_configuration = "OPTIONAL"
  tags              = local.tags
}

# -----------------------------------------------------------------------------
# Compute
# -----------------------------------------------------------------------------
module "ecs" {
  source = "../../modules/ecs"

  project                      = var.project
  environment                  = var.environment
  vpc_id                       = module.vpc.vpc_id
  public_subnet_ids            = module.vpc.public_subnet_ids
  private_subnet_ids           = module.vpc.private_subnet_ids
  alb_security_group_id        = module.vpc.alb_security_group_id
  ecs_api_security_group_id    = module.vpc.ecs_api_security_group_id
  ecs_worker_security_group_id = module.vpc.ecs_worker_security_group_id

  api_image    = var.api_image
  worker_image = var.worker_image

  # Staging: smaller footprint
  api_cpu              = 1024
  api_memory           = 2048
  api_desired_count    = 1
  api_max_count        = 3
  worker_cpu           = 512
  worker_memory        = 1024
  worker_desired_count = 1
  worker_max_count     = 2

  # Database connection
  db_host                = module.rds.address
  db_port                = module.rds.port
  db_name                = module.rds.db_name
  db_password_secret_arn = module.secrets.db_password_secret_arn

  # Redis connection
  redis_broker_host         = module.elasticache_broker.primary_endpoint
  redis_broker_port         = module.elasticache_broker.port
  redis_cache_host          = module.elasticache_cache.primary_endpoint
  redis_cache_port          = module.elasticache_cache.port
  redis_password_secret_arn = module.secrets.redis_auth_token_secret_arn

  # Auth
  cognito_user_pool_id = module.cognito.user_pool_id
  cognito_client_id    = module.cognito.client_id

  # S3
  documents_bucket_arn = module.s3.documents_bucket_arn

  # TLS
  acm_certificate_arn = var.acm_certificate_arn

  container_insights = false
  log_retention_days = 14
  tags               = local.tags
}

# -----------------------------------------------------------------------------
# Migration Drill Runner (CodeBuild inside the staging VPC)
# -----------------------------------------------------------------------------
module "migration_drill_codebuild" {
  count = var.migration_drill_github_connection_arn != "" ? 1 : 0

  source = "../../modules/codebuild"

  project                = var.project
  environment            = var.environment
  aws_region             = var.aws_region
  vpc_id                 = module.vpc.vpc_id
  private_subnet_ids     = module.vpc.private_subnet_ids
  rds_security_group_id  = module.vpc.rds_security_group_id
  repository_url         = var.migration_drill_repository_url
  github_connection_arn  = var.migration_drill_github_connection_arn
  source_version         = var.migration_drill_source_version
  buildspec_path         = "buildspecs/migration-safety-drill.yml"
  db_host                = module.rds.address
  db_port                = module.rds.port
  db_name                = module.rds.db_name
  db_user                = "alphawatch"
  db_password_secret_arn = module.secrets.db_password_secret_arn
  log_retention_days     = 14
  tags                   = local.tags
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "alb_dns_name" {
  value = module.ecs.alb_dns_name
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "ecs_api_service_name" {
  value = module.ecs.api_service_name
}

output "ecs_worker_service_name" {
  value = module.ecs.worker_service_name
}

output "frontend_bucket_id" {
  value = module.s3.frontend_bucket_id
}

output "cloudfront_distribution_id" {
  value = module.cloudfront.distribution_id
}

output "cloudfront_domain" {
  value = module.cloudfront.distribution_domain_name
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "redis_endpoint" {
  value = module.elasticache_broker.primary_endpoint
}

output "redis_cache_endpoint" {
  value = module.elasticache_cache.primary_endpoint
}

output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_client_id" {
  value = module.cognito.client_id
}

output "migration_drill_codebuild_project_name" {
  value = try(module.migration_drill_codebuild[0].project_name, null)
}

output "migration_drill_codebuild_log_group_name" {
  value = try(module.migration_drill_codebuild[0].log_group_name, null)
}
