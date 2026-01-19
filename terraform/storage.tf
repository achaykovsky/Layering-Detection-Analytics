# EFS Storage Configuration for persistent volumes

resource "aws_efs_file_system" "main" {
  count           = var.enable_efs ? 1 : 0
  creation_token  = "${var.app_name}-efs"
  encrypted       = true
  performance_mode = "generalPurpose"
  throughput_mode = var.efs_throughput_mode

  tags = {
    Name = "${var.app_name}-efs"
  }
}

resource "aws_efs_mount_target" "main" {
  count           = var.enable_efs ? length(aws_subnet.private) : 0
  file_system_id = aws_efs_file_system.main[0].id
  subnet_id      = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.efs[0].id]
}

resource "aws_security_group" "efs" {
  count       = var.enable_efs ? 1 : 0
  name        = "${var.app_name}-efs-sg"
  description = "Security group for EFS"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "NFS from ECS tasks"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.app_name}-efs-sg"
  }
}

# EFS Access Points for different directories
resource "aws_efs_access_point" "input" {
  count          = var.enable_efs ? 1 : 0
  file_system_id = aws_efs_file_system.main[0].id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/input"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = {
    Name = "${var.app_name}-efs-input"
  }
}

resource "aws_efs_access_point" "output" {
  count          = var.enable_efs ? 1 : 0
  file_system_id = aws_efs_file_system.main[0].id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/output"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = {
    Name = "${var.app_name}-efs-output"
  }
}

resource "aws_efs_access_point" "logs" {
  count          = var.enable_efs ? 1 : 0
  file_system_id = aws_efs_file_system.main[0].id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/logs"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "755"
    }
  }

  tags = {
    Name = "${var.app_name}-efs-logs"
  }
}
