###############################################################################
# Secrets Module — AIphaWatch
# Secrets Manager entries for DB credentials, API keys, and app secrets.
###############################################################################

# -----------------------------------------------------------------------------
# Database Password (auto-generated)
# -----------------------------------------------------------------------------
resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "db_password" {
  name        = "${var.project}/${var.environment}/db-password"
  description = "RDS master password for ${var.project} ${var.environment}"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-db-password"
  })
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db.result
}

# -----------------------------------------------------------------------------
# Redis Auth Token (auto-generated)
# -----------------------------------------------------------------------------
resource "random_password" "redis" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "redis_auth_token" {
  name        = "${var.project}/${var.environment}/redis-auth-token"
  description = "Redis AUTH token for ${var.project} ${var.environment}"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-redis-auth-token"
  })
}

resource "aws_secretsmanager_secret_version" "redis_auth_token" {
  secret_id     = aws_secretsmanager_secret.redis_auth_token.id
  secret_string = random_password.redis.result
}

# -----------------------------------------------------------------------------
# API Keys (placeholder secrets — values set manually or via CI)
# -----------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "alpha_vantage_key" {
  name        = "${var.project}/${var.environment}/alpha-vantage-api-key"
  description = "Alpha Vantage API key for financial data"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-alpha-vantage-key"
  })
}

resource "aws_secretsmanager_secret" "newsapi_key" {
  name        = "${var.project}/${var.environment}/newsapi-key"
  description = "NewsAPI key for news ingestion"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-newsapi-key"
  })
}

# -----------------------------------------------------------------------------
# Application Secret Key
# -----------------------------------------------------------------------------
resource "random_password" "app_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "app_secret_key" {
  name        = "${var.project}/${var.environment}/app-secret-key"
  description = "Application secret key for ${var.project} ${var.environment}"

  tags = merge(var.tags, {
    Name = "${var.project}-${var.environment}-app-secret-key"
  })
}

resource "aws_secretsmanager_secret_version" "app_secret_key" {
  secret_id     = aws_secretsmanager_secret.app_secret_key.id
  secret_string = random_password.app_secret.result
}
