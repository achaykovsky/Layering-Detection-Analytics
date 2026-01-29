# ECS Cluster and Services Configuration

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = var.ecs_cluster_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = var.ecs_cluster_name
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "services" {
  for_each = var.enable_cloudwatch_logs ? toset([
    "orchestrator",
    "layering",
    "wash-trading",
    "aggregator"
  ]) : toset([])

  name              = "/ecs/${var.app_name}/${each.key}"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.app_name}-${each.key}-logs"
  }
}

# ECS Task Definitions
locals {
  services = {
    orchestrator = {
      port           = 8000
      cpu            = var.ecs_task_cpu.orchestrator
      memory         = var.ecs_task_memory.orchestrator
      image          = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-orchestrator:${var.container_image_tag}"
      log_group      = "/ecs/${var.app_name}/orchestrator"
      env_vars = {
        PORT                    = "8000"
        INPUT_DIR               = "/app/input"
        LAYERING_SERVICE_URL    = "http://layering-service:8001"
        WASH_TRADING_SERVICE_URL = "http://wash-trading-service:8002"
        AGGREGATOR_SERVICE_URL  = "http://aggregator-service:8003"
        MAX_RETRIES             = tostring(var.max_retries)
        ALGORITHM_TIMEOUT_SECONDS = tostring(var.algorithm_timeout_seconds)
        LOG_LEVEL               = var.log_level
        RATE_LIMIT_PER_MINUTE   = tostring(var.rate_limit_per_minute)
      }
      mount_points = var.enable_efs ? [
        {
          sourceVolume  = "input"
          containerPath = "/app/input"
          readOnly      = true
        }
      ] : []
    }
    layering = {
      port      = 8001
      cpu       = var.ecs_task_cpu.layering
      memory    = var.ecs_task_memory.layering
      image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-layering:${var.container_image_tag}"
      log_group = "/ecs/${var.app_name}/layering"
      env_vars = {
        PORT                  = "8001"
        LOG_LEVEL             = var.log_level
        RATE_LIMIT_PER_MINUTE = tostring(var.rate_limit_per_minute)
      }
      mount_points = []
    }
    wash-trading = {
      port      = 8002
      cpu       = var.ecs_task_cpu.wash_trading
      memory    = var.ecs_task_memory.wash_trading
      image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-wash-trading:${var.container_image_tag}"
      log_group = "/ecs/${var.app_name}/wash-trading"
      env_vars = {
        PORT                  = "8002"
        LOG_LEVEL             = var.log_level
        RATE_LIMIT_PER_MINUTE = tostring(var.rate_limit_per_minute)
      }
      mount_points = []
    }
    aggregator = {
      port      = 8003
      cpu       = var.ecs_task_cpu.aggregator
      memory    = var.ecs_task_memory.aggregator
      image     = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_repository_name}-aggregator:${var.container_image_tag}"
      log_group = "/ecs/${var.app_name}/aggregator"
      env_vars = {
        PORT                    = "8003"
        OUTPUT_DIR              = "/app/output"
        LOGS_DIR                = "/app/logs"
        VALIDATION_STRICT       = "true"
        ALLOW_PARTIAL_RESULTS   = "false"
        LOG_LEVEL               = var.log_level
        RATE_LIMIT_PER_MINUTE   = tostring(var.rate_limit_per_minute)
      }
      mount_points = var.enable_efs ? [
        {
          sourceVolume  = "output"
          containerPath = "/app/output"
          readOnly      = false
        },
        {
          sourceVolume  = "logs"
          containerPath = "/app/logs"
          readOnly      = false
        }
      ] : []
    }
  }

  # Add secrets to env vars if enabled
  services_with_secrets = {
    for k, v in local.services : k => merge(v, {
      secrets = concat(
        # API key for all services
        var.create_secrets && var.enable_api_key_auth ? [
          {
            name      = "API_KEY"
            valueFrom = "${aws_secretsmanager_secret.api_key[0].arn}:api_key::"
          }
        ] : [],
        # Pseudonymization salt for aggregator only
        var.create_secrets && k == "aggregator" ? [
          {
            name      = "PSEUDONYMIZATION_SALT"
            valueFrom = "${aws_secretsmanager_secret.pseudonymization_salt[0].arn}:salt::"
          }
        ] : []
      )
    })
  }
}

# Task Definitions
resource "aws_ecs_task_definition" "services" {
  for_each = local.services_with_secrets

  family                   = "${var.app_name}-${each.key}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = each.value.cpu
  memory                   = each.value.memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "${each.key}-container"
      image = each.value.image

      portMappings = [
        {
          containerPort = each.value.port
          protocol      = "tcp"
        }
      ]

      environment = [
        for key, value in each.value.env_vars : {
          name  = key
          value = value
        }
      ]

      secrets = each.value.secrets

      logConfiguration = var.enable_cloudwatch_logs ? {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = each.value.log_group
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      } : null

      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:${each.value.port}/health', timeout=5).read()\" || exit 1"]
        interval    = 30
        timeout     = 10
        startPeriod = 5
        retries     = 3
      }

      mountPoints = each.value.mount_points

      essential = true
    }
  ])

  dynamic "volume" {
    for_each = var.enable_efs && each.key == "orchestrator" ? [1] : []
    content {
      name = "input"
      efs_volume_configuration {
        file_system_id     = aws_efs_file_system.main[0].id
        transit_encryption = "ENABLED"
        authorization_config {
          access_point_id = aws_efs_access_point.input[0].id
        }
      }
    }
  }

  dynamic "volume" {
    for_each = var.enable_efs && each.key == "aggregator" ? [1] : []
    content {
      name = "output"
      efs_volume_configuration {
        file_system_id     = aws_efs_file_system.main[0].id
        transit_encryption = "ENABLED"
        authorization_config {
          access_point_id = aws_efs_access_point.output[0].id
        }
      }
    }
  }

  dynamic "volume" {
    for_each = var.enable_efs && each.key == "aggregator" ? [1] : []
    content {
      name = "logs"
      efs_volume_configuration {
        file_system_id     = aws_efs_file_system.main[0].id
        transit_encryption = "ENABLED"
        authorization_config {
          access_point_id = aws_efs_access_point.logs[0].id
        }
      }
    }
  }

  tags = {
    Name = "${var.app_name}-${each.key}-task"
  }
}

# ECS Services
resource "aws_ecs_service" "services" {
  for_each = local.services_with_secrets

  name            = "${var.app_name}-${each.key}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.services[each.key].arn
  desired_count   = var.desired_count[replace(each.key, "-", "_")]
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  dynamic "load_balancer" {
    for_each = var.enable_alb ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.services[each.key].arn
      container_name   = "${each.key}-container"
      container_port   = each.value.port
    }
  }

  health_check_grace_period_seconds = 60

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  depends_on = var.enable_alb ? [aws_lb_listener.main] : []

  tags = {
    Name = "${var.app_name}-${each.key}-service"
  }
}
