#!/usr/bin/env bash
# Applique les migrations DuckDB dans l'ordre (idempotent : IF NOT EXISTS dans les .sql).
# Usage : ./migrations/run_all.sh path/vers/base.duckdb
# Requiert Python avec le package duckdb (même environnement que le projet).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="${1:?Usage: $0 <database.duckdb>}"

apply_migration() {
  local mig_path="$1"
  local name
  name="$(basename "$mig_path")"
  echo "Applying migration ${name}..."
  python - "$DB" "$mig_path" <<'PY'
import sys
from pathlib import Path

import duckdb

db_path, sql_path = sys.argv[1], Path(sys.argv[2])
conn = duckdb.connect(db_path)
try:
    conn.execute(sql_path.read_text(encoding="utf-8"))
finally:
    conn.close()
PY
}

apply_migration "$SCRIPT_DIR/add_plu_datappro.sql"
apply_migration "$SCRIPT_DIR/add_outlier_flag.sql"
echo "All migrations applied successfully."
