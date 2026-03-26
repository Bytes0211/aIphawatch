output "cluster_id" {
  description = "ECS cluster ID."
  value       = aws_ecs_cluster.main.id
}

output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "api_service_name" {
  description = "ECS API service name."
  value       = aws_ecs_service.api.name
}

output "worker_service_name" {
  description = "ECS worker service name."
  value       = aws_ecs_service.worker.name
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer."
  value       = aws_lb.api.dns_name
}

output "alb_zone_id" {
  description = "Route 53 zone ID of the ALB."
  value       = aws_lb.api.zone_id
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer."
  value       = aws_lb.api.arn
}

output "api_task_execution_role_arn" {
  description = "ARN of the ECS task execution IAM role."
  value       = aws_iam_role.task_execution.arn
}

output "api_task_role_arn" {
  description = "ARN of the ECS task IAM role."
  value       = aws_iam_role.task.arn
}
