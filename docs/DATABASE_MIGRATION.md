# Database migration: SQLite → PostgreSQL → multi-builder

What was done on 2026-11-01, how it was verified, and how to repeat or undo it.

## Starting point

- `db.sqlite3`: 610 KB, integrity check ok, 74 migrations applied; 9 projects, 5 landing pages, 7 leads,
  1 admin user, all belonging to the M3M website.
- A local PostgreSQL 18 server already held an identical copy in database `m3m` (left untouched).

## 1. Backups (nothing was deleted or overwritten)

| File | What |
| --- | --- |
| `db.sqlite3` | The original, unchanged |
| `backups/db.sqlite3.pre-multitenant-2026-11-01` | Consistent copy made with SQLite's backup API (read-only file) |
| `backups/SHA256SUMS-2026-11-01.txt` | Checksums of both |
| `backups/m3m-backup-2026-11-01_1428.tar.gz` | Full `backup.sh` archive (database + media) |
| `backups/env-sqlite-2026-11-01.bak` | The `.env` that pointed at SQLite |
| PostgreSQL `m3m_platform_pre_tenant` | The PostgreSQL copy before the multi-builder migrations |

## 2. Copy SQLite → PostgreSQL, verified row by row

```bash
# new, empty database (the old "m3m" database is not reused)
psql -U postgres -c "CREATE DATABASE m3m_platform OWNER m3m ENCODING 'UTF8' TEMPLATE template0"
DB_NAME=m3m_platform python manage.py migrate          # with the code matching the SQLite file
DB_NAME=m3m_platform python manage.py import_sqlite backups/db.sqlite3.pre-multitenant-2026-11-01
```

`import_sqlite` (core/management/commands/import_sqlite.py):

1. opens the SQLite file **read-only** (`mode=ro`);
2. refuses unless both databases are at the same migration state and the target has no leads;
3. `dumpdata` (natural keys for permissions/content types) → `flush` the fresh target → `loaddata`, keeping
   every primary key and foreign key; then moves the PostgreSQL sequences past the copied ids;
4. compares **every table, every row, every column** between the two databases.

Result: 33 tables compared, all identical. `--verify-only` against the live `db.sqlite3` also matched. The full
test suite passed on PostgreSQL, and all 24 public pages rendered byte-identical HTML from SQLite and from
PostgreSQL. Only then was `.env` switched to `DB_ENGINE=postgres`, `DB_NAME=m3m_platform`.

## 3. Multi-builder migrations

Small steps per app, each reversible:

| Migration | Does |
| --- | --- |
| `tenants 0001` | Builder, Domain, BuilderMembership tables |
| `tenants 0002_first_builder` | creates builder **M3M** (`m3m`) with domains `m3mhome.in` (primary) and `www.m3mhome.in`, both **unverified** |
| `core 0014`, `content 0005`, `projects 0030`, `leads 0011` | add `builder` (nullable) and the new fields |
| `core 0015`, `content 0006`, `projects 0031`, `leads 0012` | give every existing row to M3M; link each landing page to the project with the same slug (`is_default`, `template`); give ad-landing leads their project's landing page and every lead its `source_domain` from its `page_url` |
| `core 0016`, `content 0007`, `projects 0032`, `leads 0013` | `builder` required; unique constraints per builder / project |
| `core 0017`, `core 0018` | branding validators; M3M's logos and favicon copied from `static/` into `media/builders/m3m/branding/` and set in its settings |
| `tenants 0003_role_groups` | permission groups for the three roles |

Nothing is guessed: rows are only linked where the data already says so (same slug, the lead's own page URL).
Reconciliation report after migrating (`python manage.py check_tenant_integrity`):

```
Cross-builder links: 0
Leads without a project (general enquiries): 1      ← the homepage hero form, which never asks for one
Ad landing-page leads without a landing page, to review by hand: 0
```

The migrations were rehearsed first on a copy (`CREATE DATABASE m3m_trial TEMPLATE m3m_platform`), applied,
reversed to the previous state, and the reversed copy compared table by table with the original: all business
tables identical (only Django's own content-type/permission rows for the new models remained).

## Rolling back

| To | Do |
| --- | --- |
| PostgreSQL before multi-builder | `.env`: `DB_NAME=m3m_platform_pre_tenant`, and check out the code from before the change; or reverse in place: `migrate leads 0010 && migrate projects 0029 && migrate core 0013 && migrate content 0004 && migrate tenants zero` |
| SQLite | `.env`: `DB_ENGINE=sqlite` and the code from before the change (the file `db.sqlite3` is unchanged) |

Leads received after the switch exist only in PostgreSQL: export them first if you roll back.

## Repeating the move on a server

1. `./scripts/backup.sh` on the server (keeps `db.sqlite3` and `data.json`).
2. Create the PostgreSQL database and login (`./scripts/setup.sh --production` does it on Ubuntu).
3. With the *old* code checked out: `DB_ENGINE=postgres … manage.py migrate`, then
   `manage.py import_sqlite /path/to/copy-of-db.sqlite3` — it must say *Verified*.
4. Check out the new code, `manage.py migrate`, `manage.py check_tenant_integrity`.
5. Switch `.env`, restart, check the pages, then mark the live domain **verified** in the admin.
