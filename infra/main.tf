terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  # Uncomment and configure after creating the state bucket manually:
  backend "s3" {
     bucket = "reddit-poc-cl-581282195129-us-east-1-an"
     key    = "reddit-finance/terraform.tfstate"
     region = "us-east-1"
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

# ─── Lookups & locals ────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

data "aws_kms_alias" "ssm" {
  name = "alias/aws/ssm"
}

locals {
  task_definition_family_arn = "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/${aws_ecs_task_definition.pipeline.family}"
}

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
    value = "disabled"  # Saves ~$2-3/month; enable if you need metrics dashboard
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
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameters"]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/reddit-finance/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = data.aws_kms_alias.ssm.target_key_arn
      },
    ]
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
  cpu                      = "512"   # 0.5 vCPU
  memory                   = "1024"  # 1 GB — sufficient for Chromium + DuckDB
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
    ]

    secrets = [
      { name = "OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn },
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
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = aws_ecs_task_definition.pipeline.arn
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
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
    mode = "OFF"  # Run at exactly the scheduled time, no flexibility window
  }

  schedule_expression          = var.schedule_cron
  schedule_expression_timezone = "UTC"

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.pipeline.arn
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
      maximum_event_age_in_seconds = 3600  # Don't retry if event is >1 hour old
    }
  }
}
