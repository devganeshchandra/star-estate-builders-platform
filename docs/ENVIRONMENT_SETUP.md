# Environment and production setup

All settings come from environment variables or the `.env` file next to `manage.py` (`.env.example` lists them).
Never commit `.env`.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `DJANGO_DEBUG` | `1` | `0` in production |
| `DJANGO_SECRET_KEY` | dev key when debugging | **Required in production**; `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,.localhost` | Every builder domain (and `www.`), comma-separated. Django's first host check |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | `https://` + every builder domain |
| `PLATFORM_ADMIN_HOSTS` | `admin.localhost` | Hosts serving only `/admin/` (e.g. `admin.yourcompany.in`); optional |
| `PLATFORM_NAME` | `Builder websites` | Admin header |
| `SITE_SCHEME` | `https` | Scheme of canonical links built from each builder's primary domain |
| `TENANT_CACHE_SECONDS` | `60` | How long a web process remembers domain → builder |
| `DB_ENGINE` | `postgres` | `sqlite` only as a fallback to the old file |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | `m3m`, `m3m`, —, `localhost`, `5432` | PostgreSQL connection |
| `DB_SSLMODE` | `prefer` | `require` for a database on another server |
| `DB_CONN_MAX_AGE` | `60` | Seconds a connection is reused (health-checked before reuse) |
| `LEAD_NOTIFICATION_EMAILS` | — | Gets a copy of **every builder's** leads (your operations team). Each builder's own inbox is set in the admin |
| `LEAD_RATE_LIMIT_PER_HOUR` | `20` | Form submissions per IP address per hour |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL` | console email when debugging | SMTP for lead emails |
| `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_HSTS_SECONDS` | `1`, `0` | HTTPS redirect; HSTS once every domain is permanently on HTTPS |

Builder-specific values (phone, WhatsApp, address, logo, colours, fonts, lead inbox, GTM / GA4 / Meta pixel,
SEO) are **not** environment settings: they are in the admin, per builder.

## Production (Ubuntu 22.04 / 24.04)

```bash
git clone <repo> m3m && cd m3m && chmod +x scripts/*.sh
./scripts/setup.sh --production --domain m3mhome.in      # PostgreSQL, .env, migrate, static files
# edit .env: DJANGO_ALLOWED_HOSTS and DJANGO_CSRF_TRUSTED_ORIGINS with every builder domain
sudo ./scripts/install_server.sh m3mhome.in acehome.in xyzhome.in
```

This sets up:

- **Gunicorn** (systemd service `m3m`, 3 workers, `127.0.0.1:8000`, restarts on failure, logs in
  `journalctl -u m3m`).
- **Nginx** for every listed domain and its `www.`; a *default server* drops requests for any other host
  (HTTP 444, TLS handshake refused) before they reach Django. Uploads up to 30 MB.
- **HTTPS** with Let's Encrypt for all domains (`certbot --expand` adds new ones when you re-run the script
  with the full list). Each domain's DNS must point at the server first.

Then, for each domain, check `https://<domain>/healthz` and tick **verified** in the admin (**Domains**).
Unverified domains are never served, so a domain can be prepared before its DNS is switched.

| Concern | How |
| --- | --- |
| Static files | `collectstatic` + WhiteNoise (compressed, cache-busting names) |
| Media | `media/` on disk, served by Django under `/media/`; new uploads in `media/builders/<builder>/` |
| Database connections | persistent (`DB_CONN_MAX_AGE`) with health checks; `connect_timeout` 10 s |
| Logging | to stdout → systemd journal; requests with disallowed hosts are not logged as errors |
| Errors | builder-styled 404 page per builder; plain 404 for unknown hosts |
| Health check | `GET /healthz` → `ok` (no builder needed) or 503 if the database is down |
| Security | `ALLOWED_HOSTS` + Domain table + Nginx default server; secure cookies, HSTS (configurable), `SECURE_PROXY_SSL_HEADER`, CSRF on every form; `manage.py check --deploy` |
| Cache | in-process (no Redis needed); domain entries expire after `TENANT_CACHE_SECONDS` |
| Backups | `./scripts/backup.sh` (PostgreSQL `pg_dump` + `data.json` + media); run nightly by cron and copy off the server |

Updating: `git pull && ./scripts/update.sh` (packages, migrations, static files, restart).
After deploying, run `python manage.py check_tenant_integrity`.

Nothing in this document has been run against a server: no deployment and no DNS change has been made.
