#!/usr/bin/env bash
# Daily scheduler — fetches and analyzes new posts from r/finance_ukr.
# Intended to be run via cron. Only new (unanalyzed) posts are processed;
# already-stored posts are skipped automatically by the pipeline.
#
# Cron example (runs at 07:00 every day):
#   0 7 * * * /path/to/repo/scripts/run_daily.sh >> /path/to/repo/logs/daily.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${REPO_DIR}/logs"
LOG_FILE="${LOG_DIR}/daily.log"

mkdir -p "${LOG_DIR}"

echo "--- $(date '+%Y-%m-%d %H:%M:%S') starting ---"

cd "${REPO_DIR}"

exec poetry run python main.py
