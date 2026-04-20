#!/bin/bash
set -euo pipefail

S3_BUCKET="${S3_BUCKET:-}"
LOCAL_DB_PATH="${DB_PATH:-/app/data/insights.duckdb}"
S3_KEY="insights.duckdb"

echo "=== Reddit Finance Pipeline — $(date -u '+%Y-%m-%d %H:%M:%S UTC') ==="

# Step 1: Restore DuckDB from S3 if bucket is configured
if [ -n "$S3_BUCKET" ]; then
    echo "[entrypoint] Downloading database from s3://${S3_BUCKET}/${S3_KEY}"
    aws s3 cp "s3://${S3_BUCKET}/${S3_KEY}" "${LOCAL_DB_PATH}" 2>/dev/null \
        && echo "[entrypoint] Database restored successfully" \
        || echo "[entrypoint] No existing database found — starting fresh"
else
    echo "[entrypoint] S3_BUCKET not set — skipping download, using local database"
fi

# Step 2: Run the pipeline
cd /app
echo "[entrypoint] Starting pipeline..."
python run.py
EXIT_CODE=$?
echo "[entrypoint] Pipeline exited with code ${EXIT_CODE}"

# Step 3: Upload updated DuckDB back to S3 (always attempt, even on pipeline failure)
if [ -n "$S3_BUCKET" ] && [ -f "${LOCAL_DB_PATH}" ]; then
    echo "[entrypoint] Uploading database to s3://${S3_BUCKET}/${S3_KEY}"
    aws s3 cp "${LOCAL_DB_PATH}" "s3://${S3_BUCKET}/${S3_KEY}" \
        && echo "[entrypoint] Database uploaded successfully" \
        || echo "[entrypoint] WARNING: Failed to upload database — manual recovery may be needed"
fi

exit $EXIT_CODE
