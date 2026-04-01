#!/usr/bin/env bash
set -euo pipefail

# Phase 2 Step 1 migration drill:
# 1) backup
# 2) downgrade one revision
# 3) smoke check
# 4) upgrade to head
# 5) post-upgrade smoke check

usage() {
  cat <<'USAGE'
Usage:
  scripts/ops/migration_safety_drill.sh \
    --db-host <hostname> \
    [--db-port 5432] \
    [--db-name alphawatch] \
    [--db-user alphawatch] \
    [--db-password-secret alphawatch/staging/db-password] \
    [--aws-region us-east-1]

Notes:
- Run this from a host with network access to the target Postgres endpoint
  (for example: bastion host, ECS task shell, or CI runner in VPC).
- Requires: aws, psql, pg_dump, uv, alembic.
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

DB_HOST=""
DB_PORT="5432"
DB_NAME="alphawatch"
DB_USER="alphawatch"
DB_PASSWORD_SECRET="alphawatch/staging/db-password"
AWS_REGION="us-east-1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-host)
      DB_HOST="$2"
      shift 2
      ;;
    --db-port)
      DB_PORT="$2"
      shift 2
      ;;
    --db-name)
      DB_NAME="$2"
      shift 2
      ;;
    --db-user)
      DB_USER="$2"
      shift 2
      ;;
    --db-password-secret)
      DB_PASSWORD_SECRET="$2"
      shift 2
      ;;
    --aws-region)
      AWS_REGION="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$DB_HOST" ]]; then
  echo "--db-host is required" >&2
  usage
  exit 1
fi

require_cmd aws
require_cmd psql
require_cmd pg_dump
require_cmd uv

DB_PASS="$(aws --region "$AWS_REGION" --no-cli-pager secretsmanager get-secret-value --secret-id "$DB_PASSWORD_SECRET" --query SecretString --output text)"
if [[ -z "$DB_PASS" ]]; then
  echo "Failed to retrieve DB password from secret: $DB_PASSWORD_SECRET" >&2
  exit 1
fi

export PGPASSWORD="$DB_PASS"
export PGSSLMODE=require
export PGCONNECT_TIMEOUT=5

# Export app env vars so Alembic uses the same target.
export DB_HOST="$DB_HOST"
export DB_PORT="$DB_PORT"
export DB_NAME="$DB_NAME"
export DB_USERNAME="$DB_USER"
export DB_PASSWORD="$DB_PASS"

TS="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_FILE="/tmp/alphawatch-migration-drill-${TS}.dump"
LOG_FILE="/tmp/alphawatch-migration-drill-${TS}.log"

echo "Starting migration safety drill at $(date -u +%FT%TZ)" | tee "$LOG_FILE"
echo "Target host: $DB_HOST" | tee -a "$LOG_FILE"
echo "Backup file: $BACKUP_FILE" | tee -a "$LOG_FILE"

run_sql() {
  local sql="$1"
  psql "host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER connect_timeout=5 sslmode=require" -c "$sql"
}

echo "[1/8] Connectivity check" | tee -a "$LOG_FILE"
run_sql "select now() as connected_at;" | tee -a "$LOG_FILE"

echo "[2/8] Capture current Alembic revision" | tee -a "$LOG_FILE"
run_sql "select version_num as revision_before from alembic_version;" | tee -a "$LOG_FILE"

echo "[3/8] Create DB backup" | tee -a "$LOG_FILE"
pg_dump "host=$DB_HOST port=$DB_PORT dbname=$DB_NAME user=$DB_USER connect_timeout=5 sslmode=require" -Fc -f "$BACKUP_FILE"
echo "Backup created" | tee -a "$LOG_FILE"

echo "[4/8] Downgrade one revision" | tee -a "$LOG_FILE"
uv run alembic downgrade -1 | tee -a "$LOG_FILE"

echo "[5/8] Verify downgraded revision" | tee -a "$LOG_FILE"
run_sql "select version_num as revision_after_downgrade from alembic_version;" | tee -a "$LOG_FILE"

echo "[6/8] Smoke check after downgrade" | tee -a "$LOG_FILE"
run_sql "select count(*) as companies_count from companies;" | tee -a "$LOG_FILE"

echo "[7/8] Upgrade back to head" | tee -a "$LOG_FILE"
uv run alembic upgrade head | tee -a "$LOG_FILE"

echo "[8/8] Final revision + smoke check" | tee -a "$LOG_FILE"
run_sql "select version_num as revision_after_upgrade from alembic_version;" | tee -a "$LOG_FILE"
run_sql "select count(*) as companies_count_post_upgrade from companies;" | tee -a "$LOG_FILE"

echo "Migration safety drill completed successfully." | tee -a "$LOG_FILE"
echo "Artifacts:"
echo "- Backup: $BACKUP_FILE"
echo "- Log:    $LOG_FILE"
