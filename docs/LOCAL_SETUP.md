# Local setup (Windows + VS Code)

Run every builder's website on your own machine, with PostgreSQL, and test several domains without DNS or
certificates.

## 1. What you need

- **Python 3.12+** (python.org; tick "Add python.exe to PATH").
- **Git for Windows** (includes Git Bash, used by the `scripts/`).
- **PostgreSQL 18**, either:
  - **native** (recommended on Windows): the EnterpriseDB installer from postgresql.org. It runs as the
    Windows service `postgresql-x64-18`; start/stop it in *Services* or with
    `net start postgresql-x64-18` / `net stop postgresql-x64-18` (admin PowerShell); or
  - **Docker Desktop**: `docker compose up -d` in the project folder starts PostgreSQL 18 with its data in the
    named volume `pgdata` (kept across restarts); `docker compose stop` stops it.
- **VS Code** with the *Python* extension.

## 2. Database and login (native PostgreSQL)

Open *SQL Shell (psql)* (or `psql -U postgres`) and run, with your own password:

```sql
CREATE ROLE m3m LOGIN CREATEDB PASSWORD 'choose-a-long-password';
CREATE DATABASE m3m_platform OWNER m3m ENCODING 'UTF8' TEMPLATE template0;
```

`CREATEDB` lets `manage.py test` create its temporary test database. With Docker, the container creates the
database and login from `.env` by itself.

## 3. Project setup

In VS Code: *File → Open Folder* → the project folder. *Terminal → New Terminal*, choose **Git Bash**:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env          # then edit .env: DB_PASSWORD (and DB_NAME/DB_USER if different)
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_content        # M3M's starter content (skip if you restore a backup)
.venv/Scripts/python manage.py add_local_domains   # localhost, m3m.localhost → M3M
.venv/Scripts/python manage.py createsuperuser
.venv/Scripts/python manage.py runserver
```

(`./scripts/setup.sh` does all of this in one go.) VS Code: *Ctrl+Shift+P → Python: Select Interpreter →
.venv*, so the editor and the debugger use the project's packages.

To carry over real content instead of the starter content, see [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md)
(from an SQLite file) or use `./scripts/restore.sh backups/<backup>.tar.gz`.

## 4. Addresses

| Open | You get |
| --- | --- |
| http://localhost:8000/ | M3M |
| http://m3m.localhost:8000/ | M3M |
| http://localhost:8000/admin/ | Admin |
| http://admin.localhost:8000/admin/ | Admin on the admin-only host (no website there) |
| http://localhost:8000/healthz | `ok` when the app and database are up |

## 5. Testing several builders and domains

Chrome, Edge and Firefox send every `*.localhost` name to your own machine, so no hosts-file change is needed:

```bash
.venv/Scripts/python manage.py add_local_domains --demo     # creates sample builders ACE and XYZ
```

| Open | You get |
| --- | --- |
| http://ace.localhost:8000/ | ACE's website (starting pages, no projects yet) |
| http://xyz.localhost:8000/ | XYZ's website |
| http://nobody.localhost:8000/ | `Site not found.` (no such domain) |

Add a builder of your own in the admin (**Builders → Add**) and run `add_local_domains` again: it gets
`<slug>.localhost`. To test a real-looking name such as `acehome.in`, add it as a domain of that builder
(tick *verified*), add `acehome.in` to `DJANGO_ALLOWED_HOSTS` in `.env`, and add this line to
`C:\Windows\System32\drivers\etc\hosts` (Notepad as administrator):

```
127.0.0.1   acehome.in
```

then open http://acehome.in:8000/. Remove the line afterwards.

Things to try:

1. Log in at http://localhost:8000/admin/ as the superuser; on the **Website map** switch between builders.
2. **Projects → Add** for ACE, e.g. slug `jacob` (M3M has a `jacob` too: both are allowed).
3. **Landing pages → Add**: ACE, that project, a design, slug `jacob`, tick *Project's main page* → open
   http://ace.localhost:8000/projects/jacob. Add a second page with slug `offer` →
   http://ace.localhost:8000/projects/jacob/offer.
4. Send the form on that page; the lead appears under **Enquiries** with builder ACE, the landing page and
   `source_domain` ace.localhost. http://localhost:8000/projects/jacob/offer is "not found" on M3M.
5. Create a staff user, give them **Builder admin** for ACE only (*Who works on which builder*), log in as
   them in a private window: only ACE's data is visible.

Emails (lead notifications) are printed in the terminal while `DJANGO_DEBUG=1`.

## 6. Tests

```bash
.venv/Scripts/python manage.py test
```

Uses a temporary PostgreSQL database (`test_<DB_NAME>`) and temporary media folders; your data and `media/`
are not touched. The host `testserver` is mapped to M3M in the test database only.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Site not found.` | The host has no verified domain: run `add_local_domains`, or check **Domains** in the admin |
| `Bad Request (400)` | The host is not in `DJANGO_ALLOWED_HOSTS` (`.localhost` covers every `*.localhost`) |
| `connection refused` on port 5432 | PostgreSQL is not running (service or `docker compose up -d`) |
| `permission denied to create database` when testing | `ALTER ROLE m3m CREATEDB;` |
| A change to a domain does not show | Wait up to `TENANT_CACHE_SECONDS` (60 s) or restart `runserver` |
