# CloudWatch Monitoring and Alarms

# CloudWatch Alarms for ECS Services
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  for_each = var.enable_cloudwatch_alarms ? local.services_with_secrets : {}

  alarm_name          = "${var.app_name}-${each.key}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "This metric monitors ${each.key} service CPU utilization"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.services[each.key].name
  }

  tags = {
    Name = "${var.app_name}-${each.key}-cpu-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_memory" {
  for_each = var.enable_cloudwatch_alarms ? local.services_with_secrets : {}

  alarm_name          = "${var.app_name}-${each.key}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 85
  alarm_description   = "This metric monitors ${each.key} service memory utilization"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.services[each.key].name
  }

  tags = {
    Name = "${var.app_name}-${each.key}-memory-alarm"
  }
}

resource "aws_cloudwatch_metric_alarm" "task_count" {
  for_each = var.enable_cloudwatch_alarms ? local.services_with_secrets : {}

  alarm_name          = "${var.app_name}-${each.key}-low-task-count"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "RunningTaskCount"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "This metric monitors ${each.key} service running task count"
  treat_missing_data  = "breaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = aws_ecs_service.services[each.key].name
  }

  tags = {
    Name = "${var.app_name}-${each.key}-task-count-alarm"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  count          = var.enable_cloudwatch_alarms ? 1 : 0
  dashboard_name = "${var.app_name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      for service_name, service in local.services_with_secrets : {
        type   = "metric"
        x      = (index(keys(local.services_with_secrets), service_name) % 2) * 12
        y      = floor(index(keys(local.services_with_secrets), service_name) / 2) * 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.services[service_name].name],
            [".", "MemoryUtilization", ".", ".", ".", "."],
            [".", "RunningTaskCount", ".", ".", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "${service_name} Service Metrics"
        }
      }
    ]
  })
}
