output "documents_bucket_id" {
  description = "ID of the documents S3 bucket."
  value       = aws_s3_bucket.documents.id
}

output "documents_bucket_arn" {
  description = "ARN of the documents S3 bucket."
  value       = aws_s3_bucket.documents.arn
}

output "frontend_bucket_id" {
  description = "ID of the frontend S3 bucket."
  value       = aws_s3_bucket.frontend.id
}

output "frontend_bucket_arn" {
  description = "ARN of the frontend S3 bucket."
  value       = aws_s3_bucket.frontend.arn
}

output "frontend_bucket_regional_domain_name" {
  description = "Regional domain name of the frontend bucket for CloudFront origin."
  value       = aws_s3_bucket.frontend.bucket_regional_domain_name
}
