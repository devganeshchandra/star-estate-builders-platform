# Builder websites platform (Django)

One Django project that runs the websites of several real estate builders: **one repository, one codebase,
one shared PostgreSQL database, many domains**. Each builder (tenant) has its own domains, branding, projects,
landing pages, media, SEO, tracking and leads, kept strictly apart from every other builder's.

The first builder is **M3M**: its website, which this project started as, works exactly as before, with the
same pages, URLs, design and content. Further builders (e.g. ACE on `acehome.in`, XYZ on `xyzhome.in`) are
added in the admin, with no new code, repository or database.

| Read this | For |
| --- | --- |
| [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) | Running it on your machine (Windows + VS Code), testing several domains locally |
| [docs/MULTI_TENANT_ARCHITECTURE.md](docs/MULTI_TENANT_ARCHITECTURE.md) | How builders, domains, isolation, roles and templates work; **adding a new builder** |
| [docs/DATABASE_MIGRATION.md](docs/DATABASE_MIGRATION.md) | The SQLite → PostgreSQL move, verification and rollback |
| [docs/ENVIRONMENT_SETUP.md](docs/ENVIRONMENT_SETUP.md) | Every `.env` setting; production (Nginx, Gunicorn, HTTPS, backups) |
| [docs/DATABASE.md](docs/DATABASE.md) | The leads table, direct database access, backups |
| [docs/TECH_STACK.md](docs/TECH_STACK.md) | Technologies, tables, URLs |
| [docs/PHASE1_AUDIT.md](docs/PHASE1_AUDIT.md) | The audit of the original M3M site that this refactoring started from |

## Quick start (development)

```bash
./scripts/setup.sh                             # packages, .env, database, starter content, local domains
.venv/Scripts/python manage.py runserver       # macOS/Linux: .venv/bin/python
```

Needs PostgreSQL (native install or `docker compose up -d`). Then open:

| Address | Shows |
| --- | --- |
| http://localhost:8000/ or http://m3m.localhost:8000/ | The M3M website |
| http://ace.localhost:8000/, http://xyz.localhost:8000/ | Sample builders (after `manage.py add_local_domains --demo`) |
| http://localhost:8000/admin/ | The admin (also on http://admin.localhost:8000/admin/) |

Run the tests with `python manage.py test` (106 tests, PostgreSQL).

## Project layout

| Folder | What's inside |
| --- | --- |
| `config/` | Settings, root URLs, WSGI/ASGI, the test runner |
| `tenants/` | **Builders, domains, staff memberships**; the domain → builder middleware; access rules; provisioning of new builders; management commands |
| `core/` | Per-builder settings (contact, branding, tags), homepage text, banners, legal and menu pages, images, sitemap, `seed_content`, `import_sqlite` |
| `projects/` | Projects and their landing pages (designs in `projects/landing_pages/`, templates in `templates/projects/landing/`) |
| `content/` | Journey values and stats, press, media gallery, insights |
| `leads/` | Enquiries from every form, validation, `/api/enquiries` |
| `templates/`, `static/` | The M3M design, shared by every builder; `templates/partials/brand_head.html` adds a builder's icon, colours, fonts and tags |
| `scripts/` | `setup.sh`, `install_server.sh`, `update.sh`, `backup.sh`, `restore.sh` |
| `docker-compose.yml` | Optional local PostgreSQL |
| `media/` | Uploads (not committed). New uploads go to `media/builders/<builder>/…` |

The `app/`, `components/`, `package.json` and `node_modules/` folders are the earlier Next.js version of the M3M
site and are not used by Django (nor is `AGENTS.md`, which describes Next.js).

## How it fits together

- **Which builder?** `tenants.middleware.TenantMiddleware` reads the host name, finds its active, verified
  `Domain` and sets `request.builder`. Unknown hosts get a plain 404; there is no default builder.
- **Every query is scoped** with `.for_builder(request.builder)`; forms look up projects and landing pages
  within the builder only; the models refuse to link records of different builders.
- **Pages** are Django templates rendered on the server. A project's main landing page is at
  `/projects/<project>`, further landing pages at `/projects/<project>/<page>`.
- **Forms** post to `/api/enquiries`. The lead records the builder (from the host), project, landing page,
  source domain, UTM tags and ad click IDs. Each builder sets its own lead inbox.
- **Images** are downsized on upload and served as WebP renditions through `{% picture %}`.

## For the content team (admin guide)

Log in at `/admin/`. Someone who works for one builder only ever sees that builder; a superuser chooses the
builder at the top of the **Website map**.

- **Website map** (admin home): every page of the builder's website and where each part is edited.
- **Enquiries**: every lead, with builder, project, landing page and source domain. Filter, assign, change the
  status, export to Excel (CSV).
- **Projects**: add, edit, reorder or hide projects. Each project page is at `/projects/<slug>`.
- **Landing pages → Add**: choose the project, a design (Jacob & Co., The Cullinan, Trump Tower…) and an
  address. The page is created with the design's starting texts, pictures and lists, ready to edit in the
  *Texts*, *Images* and *Lists* tabs. Tick *Project's main page* to show it at `/projects/<project>`.
  Put `*stars*` around words for italics; `{rera}` becomes the project's RERA number.
- **Menu, footer & popup texts**: the header menu (and its Projects dropdown), footer, popup and small labels.
- **Contact & site settings**: phone, WhatsApp, address, footer, Google texts, **lead inbox**, **logo,
  favicon, colours, fonts**, social links, and **Google Tag Manager / GA4 / Meta pixel** IDs.
- **Menu pages, Homepage text, Hero banners, Insights, Press, Media, FAQs, Legal pages**: as before.
- **Billionaire Block page**: M3M's custom page at `/billionaire-block`.

Superusers also see **Builders**, **Domains** and **Who works on which builder**, and give each person a role
per builder: *Builder admin*, *Marketing manager* or *Sales* (see the architecture document).

## Put it online

See [docs/ENVIRONMENT_SETUP.md](docs/ENVIRONMENT_SETUP.md). In short, on Ubuntu 22.04 / 24.04:

```bash
./scripts/setup.sh --production --domain m3mhome.in
sudo ./scripts/install_server.sh m3mhome.in acehome.in xyzhome.in   # every builder domain
```

Nothing has been deployed and no DNS has been changed by this refactoring.
