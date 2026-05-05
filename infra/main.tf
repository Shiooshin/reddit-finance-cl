terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project = "reddit-poc"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ─── ECR ─────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "app" {
  name                 = "reddit-finance-pipeline"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ─── S3 (DuckDB storage) ─────────────────────────────────────────────────────

resource "aws_s3_bucket" "data" {
  bucket = var.s3_data_bucket
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "expire-old-data-versions"
    status = "Enabled"

    filter {
      prefix = "insights.duckdb"
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"

    filter {
      prefix = "tfstate/"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# ─── SSM Parameter Store (runtime secrets) ───────────────────────────────────

resource "aws_ssm_parameter" "openai_api_key" {
  name        = "/reddit-finance/openai_api_key"
  description = "OpenAI API key consumed by the pipeline container at task start"
  type        = "SecureString"
  value       = "REPLACE_ME"

  lifecycle {
    ignore_changes = [value]
  }
}

# ─── ECS Cluster ─────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "reddit-finance"

  setting {
    name  = "containerInsights"
    value = "disabled" # Saves ~$2-3/month; enable if you need metrics dashboard
  }
}

# ─── CloudWatch Logs ─────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "pipeline" {
  name              = "/ecs/reddit-finance-pipeline"
  retention_in_days = 30
}

# ─── IAM: Task Execution Role (ECS control plane) ────────────────────────────

resource "aws_iam_role" "task_execution" {
  name = "reddit-finance-task-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_execution_ssm" {
  name = "ssm-secrets-access"
  role = aws_iam_role.task_execution.id
  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameters"]
      Resource = aws_ssm_parameter.openai_api_key.arn
    }]
  })
}

# ─── IAM: Task Role (runtime permissions for the app) ────────────────────────

resource "aws_iam_role" "task_role" {
  name = "reddit-finance-task-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "task_s3" {
  name = "s3-duckdb-access"
  role = aws_iam_role.task_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:HeadObject",
      ]
      Resource = "${aws_s3_bucket.data.arn}/insights.duckdb"
    }]
  })
}

# ─── SES identity + send permission for the ECS task role ───────────────────

resource "aws_ses_email_identity" "sender" {
  count = var.email_from_address == "" ? 0 : 1
  email = var.email_from_address
}

data "aws_iam_policy_document" "ses_send" {
  count = var.email_from_address == "" ? 0 : 1
  statement {
    actions = [
      "ses:SendEmail",
      "ses:SendRawEmail",
    ]
    resources = [
      "arn:aws:ses:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:identity/*",
    ]
  }
}

resource "aws_iam_role_policy" "ecs_task_ses" {
  count  = var.email_from_address == "" ? 0 : 1
  name   = "ses-send"
  role   = aws_iam_role.task_role.id
  policy = data.aws_iam_policy_document.ses_send[0].json
}

# ─── Networking (default VPC) ────────────────────────────────────────────────

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "pipeline_task" {
  name        = "reddit-finance-pipeline-task"
  description = "Outbound-only SG for Fargate pipeline task"
  vpc_id      = data.aws_vpc.default.id

  egress {
    description = "Allow all outbound (Reddit API, OpenAI API, S3, ECR)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ─── ECS Task Definition ─────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "pipeline" {
  family                   = "reddit-finance-pipeline"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"  # 0.5 vCPU
  memory                   = "1024" # 1 GB — sufficient for Chromium + DuckDB
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([{
    name      = "pipeline"
    image     = var.ecr_image_uri
    essential = true

    environment = [
      # S3 bucket for DuckDB sync (entrypoint.sh reads this)
      { name = "S3_BUCKET", value = var.s3_data_bucket },
      # DB path inside the container (must match config.json storage.db_path)
      { name = "DB_PATH", value = "/app/data/insights.duckdb" },
      # Comma-separated digest recipients; deploy.yml refreshes this from
      # vars.EMAIL_RECIPIENTS on each task-def register
      { name = "EMAIL_RECIPIENTS", value = var.email_recipients },
    ]

    secrets = [

      { name = "OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.pipeline.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }

    # No port mappings needed — this is a batch job, no inbound connections
  }])

  lifecycle {
    ignore_changes = [container_definitions]
  }
}

# ─── GitHub OIDC: Deploy Role ────────────────────────────────────────────────

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    # GitHub's published thumbprints (both kept for rotation tolerance)
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

resource "aws_iam_role" "github_deploy" {
  name = "reddit-finance-github-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:ref:${var.github_main_ref}"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "ecr-push-and-ecs-register"
  role = aws_iam_role.github_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecr:GetAuthorizationToken"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:DescribeImages",
          "ecr:DescribeRepositories",
          "ecr:BatchGetImage",
        ]
        Resource = aws_ecr_repository.app.arn
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:DescribeTaskDefinition",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.task_execution.arn,
          aws_iam_role.task_role.arn,
        ]
      },
    ]
  })
}

# ─── IAM: EventBridge Scheduler Role ─────────────────────────────────────────

resource "aws_iam_role" "scheduler" {
  name = "reddit-finance-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_ecs" {
  name = "run-ecs-task"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ecs:RunTask"]

        Resource = "arn:aws:ecs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:task-definition/${aws_ecs_task_definition.pipeline.family}:*"
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.task_execution.arn,
          aws_iam_role.task_role.arn,
        ]
      },
    ]
  })
}

# ─── EventBridge Scheduler ───────────────────────────────────────────────────

resource "aws_scheduler_schedule" "daily" {
  name       = "reddit-finance-daily"
  group_name = "default"

  flexible_time_window {
    mode = "OFF" # Run at exactly the scheduled time, no flexibility window
  }

  schedule_expression          = var.schedule_cron
  schedule_expression_timezone = "Europe/Kyiv"

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.pipeline.arn_without_revision
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        assign_public_ip = true # Required for public subnet (avoids $32/mo NAT Gateway)
        subnets          = data.aws_subnets.default.ids
        security_groups  = [aws_security_group.pipeline_task.id]
      }
    }

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600 # Don't retry if event is >1 hour old
    }
  }

  lifecycle {
    ignore_changes = [target[0].ecs_parameters[0].task_definition_arn]
  }
}

