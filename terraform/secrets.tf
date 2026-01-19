# AWS Secrets Manager Configuration

resource "aws_secretsmanager_secret" "api_key" {
  count       = var.create_secrets ? 1 : 0
  name        = "${var.app_name}/${var.environment}/api-key"
  description = "API key for service authentication"

  recovery_window_in_days = 7

  tags = {
    Name = "${var.app_name}-api-key"
  }
}

resource "aws_secretsmanager_secret_version" "api_key" {
  count     = var.create_secrets ? 1 : 0
  secret_id = aws_secretsmanager_secret.api_key[0].id

  # In production, set this via AWS Console or CLI
  # terraform will not show the value in state
  secret_string = jsonencode({
    api_key = "CHANGE_ME_IN_PRODUCTION"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}

resource "aws_secretsmanager_secret" "pseudonymization_salt" {
  count       = var.create_secrets ? 1 : 0
  name        = "${var.app_name}/${var.environment}/pseudonymization-salt"
  description = "Salt for account ID pseudonymization"

  recovery_window_in_days = 7

  tags = {
    Name = "${var.app_name}-pseudonymization-salt"
  }
}

resource "aws_secretsmanager_secret_version" "pseudonymization_salt" {
  count     = var.create_secrets ? 1 : 0
  secret_id = aws_secretsmanager_secret.pseudonymization_salt[0].id

  secret_string = jsonencode({
    salt = "CHANGE_ME_IN_PRODUCTION"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
