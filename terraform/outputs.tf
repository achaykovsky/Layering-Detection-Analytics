# Terraform Outputs

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "ecs_cluster_name" {
  description = "ECS Cluster Name"
  value       = aws_ecs_cluster.main.name
}

output "ecs_cluster_arn" {
  description = "ECS Cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "alb_dns_name" {
  description = "Application Load Balancer DNS name"
  value       = var.enable_alb ? aws_lb.main[0].dns_name : null
}

output "alb_arn" {
  description = "Application Load Balancer ARN"
  value       = var.enable_alb ? aws_lb.main[0].arn : null
}

output "orchestrator_service_url" {
  description = "Orchestrator service URL"
  value       = var.enable_alb ? "http://${aws_lb.main[0].dns_name}" : null
}

output "efs_file_system_id" {
  description = "EFS File System ID"
  value       = var.enable_efs ? aws_efs_file_system.main[0].id : null
}

output "secrets_manager_secrets" {
  description = "Secrets Manager secret ARNs"
  value = var.create_secrets ? {
    api_key                = aws_secretsmanager_secret.api_key[0].arn
    pseudonymization_salt  = aws_secretsmanager_secret.pseudonymization_salt[0].arn
  } : null
  sensitive = true
}

output "cloudwatch_log_groups" {
  description = "CloudWatch Log Group names"
  value = var.enable_cloudwatch_logs ? {
    for k, v in aws_cloudwatch_log_group.services : k => v.name
  } : null
}

output "ecr_repository_urls" {
  description = "ECR repository URLs (create repositories separately)"
  value = {
    orchestrator = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-orchestrator"
    layering     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-layering"
    wash_trading = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-wash-trading"
    aggregator   = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-aggregator"
  }
}
