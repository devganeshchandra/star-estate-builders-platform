# Database

Every builder's websites share **one PostgreSQL database** (`m3m_platform` locally): every page text, project,
landing page, article, setting, admin user and every **lead** from every form, each row owned by a builder.
Pictures, brochures and floor plans are files in `media/`; the database stores where each one is.

The original SQLite file `db.sqlite3` is kept unchanged, for rolling back together with the code from before the
multi-builder change (`DB_ENGINE=sqlite`). How the data moved
and how it was verified: [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md). Settings:
[ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md).

## The leads table

Leads are in **`leads_enquiry`** (admin: *Enquiries*). One row per lead:

| Column | What it holds |
| --- | --- |
| `id` | Lead number |
| `builder_id` | The builder (→ `tenants_builder`), from the website the form was sent on |
| `source_domain` | The website address it was sent from, e.g. `m3mhome.in` |
| `project_id`, `landing_page_id` | The project (→ `projects_project`) and landing page (→ `projects_landingpage`), when known |
| `created_at`, `updated_at` | When it arrived, when it last changed |
| `lead_for` | M3M's earlier grouping: `jacob`, `cullinan`, `trump`, `billionaire` or `core` |
| `source` | Which form: `landing`, `popup`, `hero`, `contact`, `billionaire`, `brochure`… |
| `name`, `phone`, `email` | The visitor; the phone in international format (+91…) |
| `call_time`, `interest`, `residency`, `message`, `consent` | Their answers |
| `page_url`, `utm_source` … `utm_content` | The page and campaign (`utm_term` = search keyword) |
| `gclid`, `matchtype`, `fbclid`, `tbclid` | Google Ads, Meta and Taboola click details |
| `device`, `city`, `ip_address`, `user_agent` | Device, city, connection (spam checks) |
| `status`, `assigned_to_id`, `notes` | The sales team's follow-up |

The same phone number enquiring again about the same project within a day, on the same builder's site, is added
to the existing lead.

## Looking at the data directly

`python manage.py dbshell` (needs `psql`), or pgAdmin (installed with PostgreSQL). Read freely; **change data in
the admin**, which checks every value and every builder link.

```sql
-- Leads per builder and website, last 7 days
SELECT b.name, e.source_domain, count(*) FROM leads_enquiry e JOIN tenants_builder b ON b.id = e.builder_id
WHERE e.created_at > now() - interval '7 days' GROUP BY 1, 2 ORDER BY 3 DESC;

-- Leads per landing page
SELECT b.name, p.name AS project, lp.name AS page, count(*) FROM leads_enquiry e
JOIN tenants_builder b ON b.id = e.builder_id
LEFT JOIN projects_project p ON p.id = e.project_id
LEFT JOIN projects_landingpage lp ON lp.id = e.landing_page_id
GROUP BY 1, 2, 3 ORDER BY 4 DESC;
```

Times are stored in UTC; the admin and CSV export show Indian time.

## Schema changes

The schema comes from Django migrations: run `python manage.py migrate` after every code update. Never create or
alter tables by hand. `python manage.py check_tenant_integrity` confirms no record points at another builder's.

## Backups

`./scripts/backup.sh` saves one archive in `backups/`: a native PostgreSQL dump (`database.dump`, when `pg_dump`
is installed), `data.json` (loads into any database) and all uploaded files. Run it nightly and copy the archives
off the server. Restore with `./scripts/restore.sh backups/<file>.tar.gz`, or the dump with `pg_restore`.

## Security

`.env`, `backups/`, `media/` and the database hold customers' details: never commit or share them. Use a strong
`DB_PASSWORD`, keep PostgreSQL listening on localhost (or `DB_SSLMODE=require` for a remote server).
