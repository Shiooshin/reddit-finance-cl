#!/usr/bin/env bash
# Trigger a one-off pipeline run on Fargate, bypassing the EventBridge daily
# schedule. Useful for debugging, smoke-testing a fresh deploy, or pulling in
# new posts on demand.
#
# Usage:
#   scripts/run_ecs_task.sh                   # runs with defaults; tails logs
#   scripts/run_ecs_task.sh --no-follow       # don't tail logs after launch
#   scripts/run_ecs_task.sh --profile prod    # override AWS profile
#
# Requirements:
#   - aws CLI configured with a profile that has ecs:RunTask, ec2:Describe*,
#     and logs:GetLogEvents on this cluster.
#   - The task definition family `reddit-finance-pipeline` already registered
#     (the deploy workflow does this on every push to main).

set -euo pipefail

PROFILE='my-own-summer'
CLUSTER='reddit-finance'
TASK_DEF='reddit-finance-pipeline'
SG_NAME='reddit-finance-pipeline-task'
LOG_GROUP='/ecs/reddit-finance-pipeline'
FOLLOW=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      PROFILE="$2"; shift 2 ;;
    --profile=*)
      PROFILE="${1#*=}"; shift ;;
    --no-follow)
      FOLLOW=0; shift ;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

echo "[run-ecs] profile=$PROFILE cluster=$CLUSTER task-def=$TASK_DEF"

# Resolve network config (mirrors what the EventBridge scheduler uses).
SG_ID=$(aws --profile "$PROFILE" ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" \
  --query 'SecurityGroups[0].GroupId' --output text)

# Default-VPC subnets (the same set the scheduler uses).
SUBNET_IDS=$(aws --profile "$PROFILE" ec2 describe-subnets \
  --filters Name=defaultForAz,Values=true \
  --query 'Subnets[].SubnetId' --output text | tr '\t' ',')

if [[ -z "$SG_ID" || "$SG_ID" == "None" ]]; then
  echo "[run-ecs] ERROR: security group '$SG_NAME' not found" >&2
  exit 1
fi
if [[ -z "$SUBNET_IDS" ]]; then
  echo "[run-ecs] ERROR: no default-VPC subnets found" >&2
  exit 1
fi

echo "[run-ecs] sg=$SG_ID subnets=$SUBNET_IDS"

TASK_ARN=$(aws --profile "$PROFILE" ecs run-task \
  --cluster "$CLUSTER" \
  --task-definition "$TASK_DEF" \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --query 'tasks[0].taskArn' --output text)

if [[ -z "$TASK_ARN" || "$TASK_ARN" == "None" ]]; then
  echo "[run-ecs] ERROR: run-task returned no taskArn" >&2
  exit 1
fi

echo "[run-ecs] launched: $TASK_ARN"

if [[ "$FOLLOW" -eq 1 ]]; then
  echo "[run-ecs] tailing $LOG_GROUP (Ctrl-C to stop)…"
  # Give Fargate a few seconds to provision before logs appear.
  sleep 10
  exec aws --profile "$PROFILE" logs tail "$LOG_GROUP" --since 1m --follow
else
  echo "[run-ecs] tail logs manually:"
  echo "  aws --profile $PROFILE logs tail $LOG_GROUP --since 5m --follow"
fi
