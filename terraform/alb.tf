# Application Load Balancer Configuration

resource "aws_lb" "main" {
  count              = var.enable_alb ? 1 : 0
  name               = "${var.app_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb[0].id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.environment == "prod" ? true : false
  enable_http2               = true
  enable_cross_zone_load_balancing = true

  tags = {
    Name = "${var.app_name}-alb"
  }
}

# Target Groups for each service
resource "aws_lb_target_group" "services" {
  for_each = var.enable_alb ? local.services : {}

  name                 = "${var.app_name}-${each.key}-tg"
  port                 = each.value.port
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  target_type          = "ip"
  deregistration_delay = 30

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 10
    interval            = 30
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  tags = {
    Name = "${var.app_name}-${each.key}-tg"
  }
}

# ALB Listener (HTTP)
resource "aws_lb_listener" "main" {
  count            = var.enable_alb ? 1 : 0
  load_balancer_arn = aws_lb.main[0].arn
  port             = "80"
  protocol         = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services["orchestrator"].arn
  }
}

# ALB Listener (HTTPS) - if certificate provided
resource "aws_lb_listener" "https" {
  count            = var.enable_alb && var.alb_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.main[0].arn
  port             = "443"
  protocol         = "HTTPS"
  ssl_policy       = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn  = var.alb_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services["orchestrator"].arn
  }
}

# ALB Listener Rule for orchestrator (default)
resource "aws_lb_listener_rule" "orchestrator" {
  count        = var.enable_alb ? 1 : 0
  listener_arn = aws_lb_listener.main[0].arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services["orchestrator"].arn
  }

  condition {
    path_pattern {
      values = ["/orchestrate*", "/health", "/"]
    }
  }
}

# ALB Listener Rule for layering service
resource "aws_lb_listener_rule" "layering" {
  count        = var.enable_alb ? 1 : 0
  listener_arn = aws_lb_listener.main[0].arn
  priority     = 200

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services["layering"].arn
  }

  condition {
    host_header {
      values = ["layering.${var.app_name}.local"] # Update with your domain
    }
  }
}

# ALB Listener Rule for wash-trading service
resource "aws_lb_listener_rule" "wash_trading" {
  count        = var.enable_alb ? 1 : 0
  listener_arn = aws_lb_listener.main[0].arn
  priority     = 300

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services["wash-trading"].arn
  }

  condition {
    host_header {
      values = ["wash-trading.${var.app_name}.local"] # Update with your domain
    }
  }
}

# ALB Listener Rule for aggregator service
resource "aws_lb_listener_rule" "aggregator" {
  count        = var.enable_alb ? 1 : 0
  listener_arn = aws_lb_listener.main[0].arn
  priority     = 400

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.services["aggregator"].arn
  }

  condition {
    host_header {
      values = ["aggregator.${var.app_name}.local"] # Update with your domain
    }
  }
}
