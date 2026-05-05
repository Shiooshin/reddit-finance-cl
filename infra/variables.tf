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
  description = "Full ECR image URI including tag. Defaults to a public placeholder so the first apply succeeds before any image has been pushed; the deploy workflow registers real revisions."
  type        = string
  default     = "public.ecr.aws/docker/library/hello-world:latest"
}

variable "tf_state_bucket" {
  description = "S3 bucket for Terraform state (created manually, not managed here)"
  type        = string
  default     = ""
}

variable "schedule_cron" {
  description = "EventBridge Scheduler cron expression (interpreted in schedule's timezone, set in main.tf)"
  type        = string
  default     = "cron(0 20 * * ? *)" # 20:00 Europe/Kyiv daily
}

variable "github_repo" {
  description = "GitHub repository in 'owner/repo' form (used in OIDC trust policy)"
  type        = string
}

variable "github_main_ref" {
  description = "Git ref allowed to assume the deploy role (e.g. 'refs/heads/main')"
  type        = string
  default     = "refs/heads/main"
}

variable "email_from_address" {
  description = "Verified SES sender address (must be verified in the chosen region). Empty disables SES resources."
  type        = string
  default     = "reddit.finance.poc@gmail.com"
}

variable "email_recipients" {
  description = "Comma-separated digest recipients (initial value; overridden per-deploy by GitHub Actions variable EMAIL_RECIPIENTS)"
  type        = string
  default     = ""
}
