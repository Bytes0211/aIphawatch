data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  project_name = "${var.project}-${var.environment}-migration-drill"
}

resource "aws_cloudwatch_log_group" "migration_drill" {
  name              = "/aws/codebuild/${local.project_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${local.project_name}-logs"
  })
}

resource "aws_security_group" "codebuild" {
  name        = "${local.project_name}-sg"
  description = "Security group for the migration drill CodeBuild project"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${local.project_name}-sg"
  })
}

resource "aws_security_group_rule" "rds_ingress" {
  type                     = "ingress"
  from_port                = var.db_port
  to_port                  = var.db_port
  protocol                 = "tcp"
  security_group_id        = var.rds_security_group_id
  source_security_group_id = aws_security_group.codebuild.id
  description              = "Migration drill CodeBuild access"
}

resource "aws_iam_role" "codebuild" {
  name = local.project_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "codebuild.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "codebuild" {
  name = "${local.project_name}-policy"
  role = aws_iam_role.codebuild.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Effect = "Allow"
          Action = [
            "logs:CreateLogGroup",
            "logs:CreateLogStream",
            "logs:PutLogEvents"
          ]
          Resource = [
            aws_cloudwatch_log_group.migration_drill.arn,
            "${aws_cloudwatch_log_group.migration_drill.arn}:*"
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "ec2:CreateNetworkInterface",
            "ec2:CreateNetworkInterfacePermission",
            "ec2:DeleteNetworkInterface",
            "ec2:DescribeDhcpOptions",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DescribeSecurityGroups",
            "ec2:DescribeSubnets",
            "ec2:DescribeVpcs"
          ]
          Resource = "*"
        },
        {
          Effect = "Allow"
          Action = [
            "secretsmanager:GetSecretValue"
          ]
          Resource = [
            var.db_password_secret_arn
          ]
        },
        {
          Effect = "Allow"
          Action = [
            "codeconnections:UseConnection",
            "codestar-connections:UseConnection"
          ]
          Resource = var.github_connection_arn
        }
      ],
      var.source_s3_bucket_arn != "" ? [
        {
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:GetObjectVersion"
          ]
          Resource = "${var.source_s3_bucket_arn}/*"
        }
      ] : []
    )
  })
}

resource "aws_codebuild_project" "migration_drill" {
  name          = local.project_name
  description   = "Run the staging migration safety drill inside the VPC"
  service_role  = aws_iam_role.codebuild.arn
  build_timeout = var.build_timeout
  queued_timeout = var.queued_timeout

  artifacts {
    type = "NO_ARTIFACTS"
  }

  environment {
    compute_type                = var.compute_type
    image                       = var.image
    type                        = "LINUX_CONTAINER"
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_REGION"
      value = var.aws_region
    }

    environment_variable {
      name  = "DB_HOST"
      value = var.db_host
    }

    environment_variable {
      name  = "DB_PORT"
      value = tostring(var.db_port)
    }

    environment_variable {
      name  = "DB_NAME"
      value = var.db_name
    }

    environment_variable {
      name  = "DB_USER"
      value = var.db_user
    }

    environment_variable {
      name  = "DB_PASSWORD_SECRET_ARN"
      value = var.db_password_secret_arn
    }
  }

  logs_config {
    cloudwatch_logs {
      status      = "ENABLED"
      group_name  = aws_cloudwatch_log_group.migration_drill.name
      stream_name = "build"
    }
  }

  source {
    type                = "GITHUB"
    location            = var.repository_url
    git_clone_depth     = 1
    buildspec           = var.buildspec_path
    report_build_status = false

  }

  source_version = var.source_version

  vpc_config {
    vpc_id             = var.vpc_id
    subnets            = var.private_subnet_ids
    security_group_ids = [aws_security_group.codebuild.id]
  }

  tags = merge(var.tags, {
    Name = local.project_name
  })
}