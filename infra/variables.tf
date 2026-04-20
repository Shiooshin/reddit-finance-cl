variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "s3_data_bucket" {
  description = "Name of the S3 bucket to store insights.duckdb"
  type        = string
}

variable "ecr_image_uri" {
  description = "Full ECR image URI including tag (e.g. 123456.dkr.ecr.us-east-1.amazonaws.com/reddit-finance-pipeline:latest)"
  type        = string
}

variable "tf_state_bucket" {
  description = "S3 bucket for Terraform state (created manually, not managed here)"
  type        = string
  default     = ""
}

variable "schedule_cron" {
  description = "EventBridge Scheduler cron expression (UTC)"
  type        = string
  default     = "cron(0 6 * * ? *)"  # 06:00 UTC daily
}
