output "ecr_repository_url" {
  description = "ECR repository URL — use this as the base for image tags"
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "task_definition_family" {
  description = "ECS task definition family name"
  value       = aws_ecs_task_definition.pipeline.family
}

output "s3_data_bucket" {
  description = "S3 bucket name for DuckDB storage"
  value       = aws_s3_bucket.data.bucket
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for pipeline logs"
  value       = aws_cloudwatch_log_group.pipeline.name
}

output "github_deploy_role_arn" {
  description = "ARN of the IAM role assumed by GitHub Actions via OIDC"
  value       = aws_iam_role.github_deploy.arn
}

output "ssm_parameter_prefix" {
  description = "SSM parameter prefix for runtime secrets"
  value       = "/reddit-finance/"
}
