output "distribution_id" {
  description = "CloudFront distribution ID."
  value       = aws_cloudfront_distribution.frontend.id
}

output "distribution_domain_name" {
  description = "CloudFront distribution domain name."
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "distribution_hosted_zone_id" {
  description = "Route 53 hosted zone ID for the CloudFront distribution."
  value       = aws_cloudfront_distribution.frontend.hosted_zone_id
}

