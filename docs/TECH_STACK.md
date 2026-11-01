# Builder websites platform: technology overview

One repository, one language on the server (Python), no build step.

```
Visitor's browser
   │  HTML pages, CSS, a little JavaScript
   ▼
Nginx (web server: HTTPS, large uploads)            ← only on the Linux server
   ▼
Gunicorn (runs the Python app, 3 workers)           ← only on the Linux server
   ▼
Django 6.1 (Python): domain → builder, pages, admin panel, enquiry API
   ▼
Database: PostgreSQL (shared by every builder)    + media/ folder for uploads
```

## Frontend (what runs in the visitor's browser)

| Part | Technology | Notes |
| --- | --- | --- |
| Pages | **Django templates** (server-rendered HTML) | `templates/`. The server builds full HTML pages, which is good for SEO and needs no JS framework |
| Styling | **Plain CSS** | `static/css/site.css` is the original design, compiled once from the old Tailwind CSS v4 file. `static/css/django.css` holds Django-specific additions and `static/css/pages.css` the menu pages. Tailwind itself is no longer needed |
| Interactivity | **Vanilla JavaScript** (no framework) | `static/js/site.js`: header, enquiry popup, banner slideshow, Journey tabs, news popup, 3-step project discovery, form sending, project/gallery/insight filters, lightbox, sticky section tabs, scroll reveals |
| Smooth scrolling | **Lenis 1.3.27** + **GSAP 3.15** (ScrollTrigger) | Copied into `static/vendor/`, same as the old site |
| Phone validation | **libphonenumber-js** | `static/vendor/`. Validates Indian and international numbers |
| Fonts | **Google Fonts**: Roboto (headings), Open Sans (text) | Same fonts as before |
| Popups | Native HTML `<dialog>` | No library needed |
| Images | WebP copies at 480/828/1200/1920px, chosen per screen size (`srcset`) | Created automatically by the `{% picture %}` template tag (replaces `next/image`) |

No longer used: Node.js, Next.js, React, Framer Motion and the Tailwind build.

## Backend (what runs on the server)

| Part | Technology | Version |
| --- | --- | --- |
| Language | **Python** | 3.12 or newer (3.12 on Ubuntu 24.04; developed on 3.15) |
| Web framework | **Django** | 6.1.2 |
| Admin panel | **Django admin** with the **django-unfold** theme | 0.110.0 |
| Image processing | **Pillow** | 13.0.0: resizes uploads, makes WebP copies |
| Phone validation (server) | **phonenumbers** | 9.0.41: same rules as the browser |
| Static files | **WhiteNoise** | 6.12.0: compressed, cached CSS/JS/images |
| Settings | **python-dotenv** | 1.2.4: reads the `.env` file |
| App server (Linux) | **Gunicorn** | 23.0.0 |
| Web server (Linux) | **Nginx** | from Ubuntu's package manager |
| HTTPS certificate | **Let's Encrypt** (certbot) | free and auto-renewing |
| Background service | **systemd** | starts the site on boot and restarts it if it crashes |

### Django apps (folders)

| App | Responsible for |
| --- | --- |
| `tenants` | Builders, domains, staff memberships and roles; the domain → builder middleware; access rules; new-builder provisioning; `create_builder`, `add_local_domains`, `check_tenant_integrity` |
| `core` | Site settings (phone, WhatsApp, address, footer), homepage text, hero banners, pages (privacy…), image helpers, sitemap, robots.txt, 404 page, `seed_content` command |
| `projects` | Projects and their landing pages: highlights, configurations/floor plans, gallery, brochure, map, SEO fields |
| `content` | Journey values and statistics, press/news items, media gallery, insights |
| `leads` | Enquiries from all forms, validation, `/api/enquiries`, email alerts, CSV export |

### Website addresses

| URL | What it is |
| --- | --- |
| `/` | Homepage (teasers: 3 projects, 8 gallery images, 3 news items, 3 insights) |
| `/projects` | All projects in three collections: Now Presenting, On the Horizon, Delivered Landmarks |
| `/projects/<slug>` | The project's main landing page, e.g. `/projects/m3m-trump-tower-noida` |
| `/projects/<slug>/<page>` | A further landing page of the project (e.g. one per campaign) |
| `/our-journey` | Story, philosophy, values, milestones timeline, signature projects |
| `/media-centre` | Filterable gallery with lightbox, films (YouTube), press coverage |
| `/insights` | Featured article and all articles, filterable by topic |
| `/insights/<slug>` | Article page |
| `/contact` | Call back form, contact details, map, FAQs |
| `/privacy`, `/disclaimer`, `/compliance` | Text pages managed in the admin |
| `/admin/` | Admin panel |
| `/api/enquiries` | Receives the enquiry forms (POST only); the builder comes from the host name |
| `/healthz` | Health check for monitoring (no builder needed) |
| `/sitemap.xml`, `/robots.txt` | For search engines |
| `/styleguide` | Design reference (hidden from Google) |

## Database

- **PostgreSQL** (18 locally): one database shared by every builder, each row owned by a builder
  ([MULTI_TENANT_ARCHITECTURE.md](MULTI_TENANT_ARCHITECTURE.md)). Guide: [DATABASE.md](DATABASE.md); the move
  from SQLite: [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md).
- **SQLite**: the original `db.sqlite3` is kept unchanged, for a rollback with the previous code.
- **Uploaded files** (images, brochures, floor plans) are not in the
  database. They are in the `media/` folder. Back up both.

### Tables

| Table (model) | Holds |
| --- | --- |
| `SiteSettings` (one row) | Phone, WhatsApp, address, footer text, SEO defaults, thank-you message |
| `HomePage` (one row) | Every heading/paragraph on the homepage |
| `HeroBanner` | Homepage banner images (2+ = slideshow) |
| `InnerPage` | Banner image, headings, intro and SEO text for each menu page |
| `FAQ` | Questions on the Contact page |
| `Page` | Privacy / Disclaimer / Compliance text |
| `Project` | Name, slug, category, residential/commercial, offering, location, city, RERA, image, summary, landing-page text, brochure, map, SEO, order, visible |
| `ProjectHighlight`, `ProjectConfiguration`, `ProjectImage` | Landing-page sections per project |
| `LandingPage`, `LandingText`, `LandingImage`, `LandingItem` | Content of the custom ad landing pages (Jacob & Co., The Cullinan, Trump Tower, Billionaire Block): every text, fixed image and list, plus SEO |
| `JourneyPrinciple`, `JourneyStat`, `Milestone` | "Our Journey" values, numbers and timeline |
| `PressItem`, `MediaImage`, `Video` | Press coverage, gallery (with categories), YouTube films |
| `Insight` | Articles: category, summary, body with sub-headings, author, date |
| `Builder`, `Domain`, `BuilderMembership` | The builders (tenants), their domains, and who works on which builder in which role |
| `Enquiry` | Every lead: builder, source domain, landing page, form, project, name, phone (international format), email, call time, interest, residency, consent, page, UTM campaign tags, IP, browser, status, assigned salesperson, notes, date |
| Django built-ins | Admin users, groups and permissions, login sessions, change history |

## Security built in

- CSRF protection on every form, and an admin login with Django's password rules.
- Server-side validation of every enquiry; a hidden honeypot field and a
  per-IP hourly limit against spam.
- In production: HTTPS redirect, secure cookies, `ALLOWED_HOSTS` check,
  secret key kept in `.env` (never in the code).

## Helper scripts (`scripts/`)

| Script | Use |
| --- | --- |
| `setup.sh` | Set up on any machine: Python check (installs it on Ubuntu if missing), packages, `.env` with a new secret key, database, starter content, admin account. `--production --domain …` for servers |
| `install_server.sh` | Ubuntu server: Gunicorn service + Nginx + optional HTTPS |
| `update.sh` | After pulling new code: packages, migrations, static files, restart |
| `backup.sh` | Database + uploads in one `.tar.gz` file (to move machines or keep copies) |
| `restore.sh` | Load a backup onto this machine (replaces current content) |
