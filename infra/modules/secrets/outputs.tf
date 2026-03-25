output "db_password" {
  description = "Generated database password."
  value       = random_password.db.result
  sensitive   = true
}

output "db_password_secret_arn" {
  description = "ARN of the Secrets Manager secret for the DB password."
  value       = aws_secretsmanager_secret.db_password.arn
}

output "alpha_vantage_key_secret_arn" {
  description = "ARN of the Secrets Manager secret for the Alpha Vantage API key."
  value       = aws_secretsmanager_secret.alpha_vantage_key.arn
}

output "newsapi_key_secret_arn" {
  description = "ARN of the Secrets Manager secret for the NewsAPI key."
  value       = aws_secretsmanager_secret.newsapi_key.arn
}

output "app_secret_key_secret_arn" {
  description = "ARN of the Secrets Manager secret for the app secret key."
  value       = aws_secretsmanager_secret.app_secret_key.arn
}
