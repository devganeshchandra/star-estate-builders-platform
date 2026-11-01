#!/usr/bin/env bash
# Save all website content (database + uploaded images/files) into one file,
# plus a ready-to-use copy of the database itself: db.sqlite3 on SQLite, or a
# native dump (database.dump) on PostgreSQL. Safe to run while the site is live,
# e.g. nightly or to move the site to another machine.
#
#   ./scripts/backup.sh                  -> backups/m3m-backup-YYYY-MM-DD_HHMM.tar.gz
#
# Restore it with ./scripts/restore.sh <file>.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -x .venv/bin/python ]]; then PY=".venv/bin/python"; else PY=".venv/Scripts/python"; fi

stamp="$(date +%Y-%m-%d_%H%M)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p backups

"$PY" manage.py dumpdata \
  --natural-foreign --natural-primary --indent 1 \
  --exclude contenttypes --exclude auth.permission \
  --exclude sessions --exclude admin.logentry \
  --output "$work/data.json"

mkdir -p media
cp -r media "$work/media"
files=(data.json media)

set -a; [[ -f .env ]] && source .env; set +a
if [[ ! "${DB_ENGINE:-postgres}" =~ ^postgres ]]; then
  # SQLite's own backup: a consistent copy even while visitors are sending leads (copying the file is not safe).
  copy_to="$(cygpath -w "$work/db.sqlite3" 2>/dev/null || echo "$work/db.sqlite3")"
  "$PY" manage.py shell -c "
import sqlite3
from django.db import connection
connection.ensure_connection()
copy = sqlite3.connect(r'$copy_to')
connection.connection.backup(copy)
copy.close()
" >/dev/null
  files+=(db.sqlite3)
elif command -v pg_dump >/dev/null; then
  # On PostgreSQL, a native dump (pg_restore can load it into any PostgreSQL server).
  PGPASSWORD="${DB_PASSWORD:-}" pg_dump --format=custom --no-owner     --host="${DB_HOST:-localhost}" --port="${DB_PORT:-5432}" --username="${DB_USER:-m3m}"     --file="$work/database.dump" "${DB_NAME:-m3m}"
  files+=(database.dump)
fi

archive="backups/m3m-backup-$stamp.tar.gz"
tar -czf "$archive" -C "$work" "${files[@]}"
echo "Backup saved: $archive"
