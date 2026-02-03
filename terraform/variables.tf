# Variable definitions for Terraform deployment

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "app_version" {
  description = "Application version tag"
  type        = string
  default     = "0.1.0"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "layering-detection"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# ECS Configuration
variable "ecs_cluster_name" {
  description = "Name of ECS cluster"
  type        = string
  default     = "layering-detection-cluster"
}

variable "ecs_task_cpu" {
  description = "CPU units for ECS tasks (1024 = 1 vCPU)"
  type        = map(number)
  default = {
    orchestrator = 512
    layering     = 512
    wash_trading = 512
    aggregator   = 512
  }
}

variable "ecs_task_memory" {
  description = "Memory (MB) for ECS tasks"
  type        = map(number)
  default = {
    orchestrator = 1024
    layering     = 512
    wash_trading = 512
    aggregator   = 512
  }
}

variable "desired_count" {
  description = "Desired task count per service"
  type        = map(number)
  default = {
    orchestrator = 1
    layering     = 2
    wash_trading = 2
    aggregator   = 1
  }
}

variable "min_capacity" {
  description = "Minimum task count for auto-scaling"
  type        = map(number)
  default = {
    orchestrator = 1
    layering     = 1
    wash_trading = 1
    aggregator   = 1
  }
}

variable "max_capacity" {
  description = "Maximum task count for auto-scaling"
  type        = map(number)
  default = {
    orchestrator = 5
    layering     = 10
    wash_trading = 10
    aggregator   = 5
  }
}

# Container Image Configuration
variable "ecr_repository_name" {
  description = "ECR repository name prefix"
  type        = string
  default     = "layering-detection"
}

variable "container_image_tag" {
  description = "Container image tag"
  type        = string
  default     = "latest"
}

# Application Configuration
variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "max_retries" {
  description = "Maximum retry attempts for orchestrator"
  type        = number
  default     = 3
}

variable "algorithm_timeout_seconds" {
  description = "Timeout for algorithm service calls"
  type        = number
  default     = 30
}

variable "rate_limit_per_minute" {
  description = "Rate limit per minute for services"
  type        = number
  default     = 100
}

# Security Configuration
variable "enable_api_key_auth" {
  description = "Enable API key authentication"
  type        = bool
  default     = true
}

variable "create_secrets" {
  description = "Create secrets in AWS Secrets Manager"
  type        = bool
  default     = true
}

# Storage Configuration
variable "enable_efs" {
  description = "Enable EFS for persistent storage (input/output/logs)"
  type        = bool
  default     = true
}

variable "efs_throughput_mode" {
  description = "EFS throughput mode (provisioned or bursting)"
  type        = string
  default     = "bursting"
}

# Monitoring Configuration
variable "enable_cloudwatch_logs" {
  description = "Enable CloudWatch Logs"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "enable_cloudwatch_alarms" {
  description = "Enable CloudWatch alarms"
  type        = bool
  default     = true
}

# Load Balancer Configuration
variable "enable_alb" {
  description = "Enable Application Load Balancer"
  type        = bool
  default     = true
}

variable "alb_certificate_arn" {
  description = "ARN of SSL certificate for ALB (optional, for HTTPS)"
  type        = string
  default     = ""
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access ALB (HTTP/HTTPS). For production (environment = prod), use specific CIDRs only; 0.0.0.0/0 is rejected by a precondition in security.tf."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}
