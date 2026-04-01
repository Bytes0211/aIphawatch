output "project_name" {
  description = "Name of the migration drill CodeBuild project."
  value       = aws_codebuild_project.migration_drill.name
}

output "project_arn" {
  description = "ARN of the migration drill CodeBuild project."
  value       = aws_codebuild_project.migration_drill.arn
}

output "security_group_id" {
  description = "Security group ID used by the migration drill CodeBuild project."
  value       = aws_security_group.codebuild.id
}

output "log_group_name" {
  description = "CloudWatch log group name for the migration drill CodeBuild project."
  value       = aws_cloudwatch_log_group.migration_drill.name
}