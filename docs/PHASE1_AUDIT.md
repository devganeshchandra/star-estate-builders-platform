# Phase 1 audit: M3M website → multi-builder platform

> **Outcome (2026-11-01).** Decisions taken: PostgreSQL as the primary database; M3M's domains are the ones in
> the brief (`m3mhome.in`; the official m3mindia.com domain is left out); admin on every builder domain plus an
> optional admin-only host; Billionaire Block kept as an M3M custom page; Next.js leftovers left in place.
> Phases 2–9 are implemented: see [MULTI_TENANT_ARCHITECTURE.md](MULTI_TENANT_ARCHITECTURE.md) and
> [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md). The text below is the audit as written before any change.

Date: 2026-11-01 · Scope: read-only inspection of the repository, `db.sqlite3` and the local PostgreSQL
database. No code, data or configuration was changed in Phase 1 (this file is the only addition).

---

## 1. Summary

The site is a clean, server-rendered **Django 6.1.2** project (four apps: `core`, `projects`, `content`,
`leads`) with an Unfold-themed admin. It is already **PostgreSQL-compatible**: the full test suite
(70 tests) passes on both SQLite and the local PostgreSQL 18 server. The data set is small (9 projects,
5 landing pages, 7 leads, 1 admin user) and belongs entirely to M3M, so moving it to a first tenant does not
require guessing ownership of any record.

The main obstacle to multi-tenancy is not the database but **global singletons and global uniqueness**:
site settings, homepage text and the Billionaire Block page are forced to row `pk=1`; project, landing-page,
legal-page and article slugs are unique across the whole database; and landing pages are linked to projects
only by matching slugs and template file names. Every one of these needs a builder dimension.

Baseline verified on 2026-11-01:

| Check | Result |
| --- | --- |
| `manage.py test` on SQLite | **70 tests, OK** |
| `manage.py test` on local PostgreSQL 18.6 (temporary `test_m3m` DB) | **70 tests, OK** |
| `manage.py makemigrations --check` | No changes detected (models and migrations in step) |
| `manage.py check` | No issues |
| `PRAGMA integrity_check` on `db.sqlite3` | ok (WAL mode) |

---

## 2. Existing architecture

```
Browser ──► (Nginx ─► Gunicorn, Linux only) ──► Django 6.1.2 ──► SQLite db.sqlite3  (+ media/ on disk)
                                                     │
                                                     └─ WhiteNoise for /static, django.views.static.serve for /media
```

| Item | Detail |
| --- | --- |
| Python / Django | Python 3.15 (local venv), Django 6.1.2, django-unfold 0.110.0, Pillow 13, phonenumbers, WhiteNoise, python-dotenv, psycopg 3.3.6 |
| Settings | `config/settings.py`, everything from `.env`; `DB_ENGINE=sqlite|postgres` switch already exists |
| Templates | `templates/` (Django templates, no JS framework); plain CSS + vanilla JS in `static/`, GSAP/Lenis vendored |
| Cache | `LocMemCache` (per process) — used for singletons, image renditions and the lead rate limit |
| Deploy scripts | `scripts/setup.sh`, `install_server.sh` (systemd + Gunicorn ×3 + Nginx + certbot), `update.sh`, `backup.sh`, `restore.sh` |
| Leftovers | A previous **Next.js** version still sits in the repo: `app/`, `components/`, `package.json`, `next.config.ts`, `node_modules/`, `.next/`, and `AGENTS.md` (which describes Next.js and is now misleading). None of it is used by Django. |

### Apps and models

| App | Models | Notes |
| --- | --- | --- |
| `core` | `SiteSettings` *(singleton)*, `HomePage` *(singleton)*, `HeroBanner`, `Page` (legal pages), `InnerPage` (5 menu pages, `key` unique), `FAQ` | `SingletonModel` forces `pk=1` ([core/models.py:17](../core/models.py#L17)) with a global cache key |
| `projects` | `Project` (+ `ProjectHighlight`, `ProjectConfiguration`, `ProjectImage`), `BillionaireBlockPage` *(singleton)* + `BillionaireResidence`, `BillionaireItem`, `BillionaireNews`, `LandingPage` + `LandingText`, `LandingImage`, `LandingItem` | `Project.slug` and `LandingPage.slug` globally unique |
| `content` | `JourneyPrinciple`, `JourneyStat`, `Milestone`, `Publication`, `PressItem`, `MediaImage`, `Video`, `Insight` | All M3M corporate content, no owner field; `Insight.slug`, `Publication.name` globally unique |
| `leads` | `Enquiry` | FK to `Project` (nullable) and `auth.User` (`assigned_to`); full UTM/click-ID tracking |

### URLs (all on one host today)

| URL | View | Content source |
| --- | --- | --- |
| `/` | `core.views.home` | `HomePage`, banners, featured projects, press, media, insights, Billionaire teaser |
| `/projects` | `projects.views.project_list` | published `Project`s by status |
| `/projects/<slug>` | `projects.views.project_detail` | standard template, **or** `templates/projects/landing/<slug>.html` when a `LandingPage` with the same slug exists ([projects/views.py:59](../projects/views.py#L59)) |
| `/billionaire-block` | `projects.views.billionaire_block` | `BillionaireBlockPage` singleton + `LandingPage("billionaire-block")` |
| `/our-journey`, `/media-centre`, `/contact` | `core.views.*` | `InnerPage` + content app |
| `/insights`, `/insights/<slug>` | `content.views.*` | `Insight` |
| `/<slug>` (catch-all, last) | `core.views.page` | `Page` (privacy, disclaimer, compliance) |
| `/api/enquiries` (POST) | `leads.views.submit_enquiry` | creates `Enquiry` |
| `/sitemap.xml`, `/robots.txt`, `/styleguide`, `/admin/`, `/media/…` | | |

### How landing pages work today

* Each custom landing page has a Python module in `projects/landing_pages/` (`jacob`, `cullinan`, `trump`,
  `billionaire`, `site`) listing its text/image/list slots and starting content.
* `projects/landing.py: seed()` turns them into `LandingPage` / `LandingText` / `LandingImage` /
  `LandingItem` rows from a migration; content is then edited in the admin.
* The link between a project and its landing page is **implicit**: same slug, plus a template file named
  after the slug. There is no foreign key.
* `LandingPage("website-texts")` is not a landing page at all — it holds the header menu, footer and popup
  texts for the whole site (read by `core.context_processors.site` on every request).
* Billionaire Block is **not a `Project` row**; it is its own singleton page with its own route.

### Lead flow

1. Every form posts to `/api/enquiries` with hidden `source`, `page_url`, UTM and click-ID fields
   (`templates/partials/form_tracking.html`, `static/js/site.js` keeps them for the visit).
2. `EnquiryForm` validates per `source`; the project is looked up **by slug across all projects**
   ([leads/forms.py:109](../leads/forms.py#L109)).
3. Honeypot → silent OK; per-IP hourly rate limit (LocMem cache).
4. Landing leads from the same phone + project within 24 h are merged
   ([leads/views.py:55](../leads/views.py#L55)).
5. `lead_for` is derived by keyword-matching the project category against a hardcoded list
   (Jacob / Cullinan / Trump / Billionaire / Core) ([leads/models.py:45](../leads/models.py#L45)).
6. Email to `LEAD_NOTIFICATION_EMAILS` (one global list).

### Admin and permissions

* One superuser (`admin`). One group, **Website editors** (created by migration `core/0013`), with global
  add/change/delete on all content and view/change/delete on enquiries; it has no members yet.
* The Unfold sidebar in `config/settings.py` is hardcoded to M3M: title "M3M India Admin", M3M favicon, and
  links to specific landing-page slugs ([config/settings.py:273-277](../config/settings.py#L273-L277)).
* `core/site_map.py` (admin dashboard "Website map" and the on-site "Edit this page" button) also lists the
  M3M landing pages by slug.

### Integrations

No analytics or ad pixels (GTM / GA4 / Meta / Taboola) are hardcoded in templates. Only one Microsoft
Clarity reference exists in the Cullinan landing page/JS. Tracking today is **capture of ad parameters into
leads**, not client-side pixels. Email uses Django SMTP. Google Maps embeds are admin-editable URLs.

---

## 3. Data inventory

### `db.sqlite3` (610 KB, integrity ok, all 74 migrations applied incl. the uncommitted `leads/0009`, `0010`)

| Table | Rows | | Table | Rows |
| --- | ---: | --- | --- | ---: |
| `projects_project` | 9 | | `projects_landingtext` | 600 |
| `projects_landingpage` | 5 | | `projects_landingitem` | 302 |
| `projects_landingimage` | 31 | | `projects_billionaireitem` | 130 |
| `projects_billionaireresidence` | 3 | | `projects_billionairenews` | 4 |
| `leads_enquiry` | 7 | | `content_insight` | 11 |
| `content_mediaimage` | 13 | | `content_pressitem` / `publication` | 7 / 4 |
| `core_innerpage` | 5 | | `core_page` | 3 (only `disclaimer` published) |
| `core_herobanner` / `faq` | 2 / 5 | | `auth_user` | 1 (superuser) |
| `projects_projecthighlight` / `configuration` / `image` | 0 / 0 / 0 | | `content_video` | 0 |

Projects (all published, all "current"): `m3m-jacob-co-residences`, `m3m-jacob-jewel-crest-noida`,
`m3m-the-line-retail-shops`, `m3m-the-line-pentsuites`, `m3m-the-cullinan-residential`,
`m3m-the-cullinan-avenue`, `smartworld-noida-residential`, `smartworld-noida-commercial`, `m3m-trump-tower-noida`.

Landing pages: `m3m-jacob-co-residences`, `m3m-the-cullinan-residential`, `m3m-trump-tower-noida`
(each matches a project), `billionaire-block` (no project), `website-texts` (site-wide).

Leads: 7 rows, latest 2026-10-29 — `contact`×2, `guided`, `hero` (no project), `landing`→Jacob,
`landing`→Trump, `popup`→Trump. Every lead belongs to M3M (there is only one tenant), so the builder can be
set on all of them with certainty. The one lead with no project stays project-less.

### Local PostgreSQL

A PostgreSQL **18.6** Windows service (`postgresql-x64-18`) is running. Its `m3m` database holds an identical
copy of the data (same row counts, same latest lead, same 74 migrations). Credentials are in
`backups/env-postgres-2026-10-31.bak`. Docker is **not** installed.

### Backups already present (`backups/`, git-ignored)

Six `backup.sh` archives (latest `m3m-backup-2026-10-31_1604.tar.gz`, ~144 MB incl. media),
`db.sqlite3.before-switch-2026-10-31`, and the saved PostgreSQL `.env`.

### Media (140 MB, not in git)

`media/{banners, billionaire-block, insights, landing/<page-slug>, media-gallery, page-banners, press,
projects, renditions}`. Upload paths have no builder prefix. Everything under `/media/` is publicly served
by Django ([config/urls.py:23](../config/urls.py#L23)), including the "gated" Billionaire brochure PDF.

---

## 4. Important finding: the database direction was reversed yesterday

Last commit (`0edda0c`, 30 Oct) made **PostgreSQL the production database**. The **uncommitted** working tree
(31 Oct) switches back to **SQLite**: `.env` → `DB_ENGINE=sqlite`, `.env.example`, `config/settings.py`
(WAL/IMMEDIATE tuning), `docs/DATABASE.md` ("no database server to install, run or pay for"),
`scripts/backup.sh`. The same uncommitted change set also contains real feature work (ad click tracking,
`lead_for`, migrations `leads/0009`, `0010`).

This brief asks for PostgreSQL again. I will follow the brief, but the reason for yesterday's switch (hosting
cost? server setup?) should be known before production planning. It does not block local work.

---

## 5. M3M-specific vs reusable components

### Hardcoded M3M values (must become builder data)

| Where | What |
| --- | --- |
| `config/settings.py` | `SITE_URL=https://www.m3mindia.com` (used for canonical, `og:url`, sitemap, JSON-LD); `DEFAULT_FROM_EMAIL`; Unfold title/favicon/sidebar slugs |
| `core/models.py` field defaults | M3M phone, WhatsApp, address, map, copy (defaults only; real values are in the DB row) |
| `leads/models.py` | `Enquiry.LeadFor` enum and `lead_for_of()` keyword matching on Jacob/Cullinan/Trump |
| `core/site_map.py` | landing-page entries listed by M3M slug |
| `projects/models.py:545` | `LandingPage.get_absolute_url` special-cases `billionaire-block` / `website-texts` |
| `templates/base.html:42` | preloader text "M3M"; favicons from `static/images/logo/` |
| `templates/partials/header.html`, `footer.html`, `home/*.html`, landing templates | logo files and some "M3M" copy |
| `projects/landing_pages/*.py` | M3M starting content (fine: seed data for the M3M tenant) |
| `static/css/*.css` | the M3M palette (ink/ivory/champagne) as fixed values |

### Reusable as-is or with small changes

* Lead validation (`leads/validation.py`), form tracking partial, UTM/click-ID capture, CSV export.
* Image pipeline (`ResizingImageField`, WebP renditions, `{% picture %}`).
* Landing-page content engine (`LandingPage` + texts/images/lists + Python slot modules): it is already a
  generic "template + editable slots" system — the right shape for reusable templates across builders.
* Project model and standard project page (`projects/detail.html`).
* Menu-page (`InnerPage`) pattern, sitemap classes, robots, 404.
* Deploy scripts (need multi-domain `server_name` and per-domain certificates).

### Needs modification

* Every content model: add a builder owner.
* Singletons → one row per builder.
* Global unique slugs/keys → unique per builder (or per project).
* Context processor, views, sitemap, robots, lead form/view: resolve everything through `request.builder`.
* Admin: tenant scoping, roles, a sidebar built from data instead of hardcoded slugs.
* Settings: `SITE_URL` → per-request primary domain; `ALLOWED_HOSTS` per environment.

---

## 6. Risks and breaking changes

| # | Risk | Impact | Mitigation |
| --- | --- | --- | --- |
| R1 | **Singletons at `pk=1`** with global cache keys | Second builder would overwrite M3M's settings/homepage | Convert to `OneToOne(Builder)`; cache key includes builder id; M3M keeps row 1 |
| R2 | **Global unique slugs** (`Project`, `LandingPage`, `Page`, `Insight`, `InnerPage.key`, `Publication.name`) | ACE cannot create `jacob`; unique-index swaps can fail mid-migration | Three-step migrations: add nullable FK → backfill M3M → make NOT NULL and swap to `UniqueConstraint(builder, slug)` |
| R3 | Project ↔ landing page linked **by slug and template filename** | Renaming/duplicating breaks pages silently | Add explicit `LandingPage.project` FK + `template` field; keep slug-named template files working as a fallback for M3M |
| R4 | **Cross-tenant lead submission**: project looked up by slug globally | Once ACE exists, an M3M form could attach a lead to an ACE project (IDOR) | Look up only within `request.builder`; set `builder` from the host, never from POST |
| R5 | Lead de-duplication query not scoped | Merge across tenants | Scope by builder |
| R6 | `lead_for` hardcoded enum | Meaningless for other builders | Keep the column for M3M history; add `landing_page` FK + `source_domain`; new reporting by builder/project/landing page |
| R7 | `LocMemCache` per Gunicorn worker | Domain→builder cache and singletons go stale in other workers after an admin edit | Short TTL (≈60 s) + invalidation on save; or switch to Django's `DatabaseCache` (no new infrastructure) |
| R8 | `/media/` all public, no builder prefix | Private files (brochures) readable by URL; name collisions between builders | New uploads under `builders/<slug>/…`; existing paths untouched; gated files served by a view that checks the builder (later phase) |
| R9 | Catch-all `/<slug>` route | A builder page slug could shadow future routes | Unchanged behaviour; reserved-slug validation |
| R10 | Admin users have global permissions | Builder staff would see all builders | Membership + role model; admin mixin filters querysets, FK choices and saves |
| R11 | Unknown Host headers | Host-header injection, cache poisoning | `ALLOWED_HOSTS` + Domain table + Nginx default server that rejects unknown hosts; no fallback builder |
| R12 | Data migration SQLite → PostgreSQL | Sequence values, content types, permissions | `dumpdata` excluding `contenttypes`/`auth.permission`, `loaddata`, `sqlsequencereset`, per-table count + checksum comparison script |
| R13 | Uncommitted work in the tree | A refactor on top of it makes rollback hard | Commit it as a checkpoint before Phase 2 (needs your OK) |
| R14 | Billionaire Block special-casing | Hard to generalise | Keep it as an M3M custom page owned by the M3M builder in the first pass; convert later if wanted |

---

## 7. Proposed target model (for review; nothing implemented yet)

New app **`tenants`**:

```
Builder(id, name, slug unique, is_active, created_at, updated_at)
  ├─ Domain(builder FK, domain unique (lower-cased, no port, no trailing dot), is_primary, is_verified, is_active)
  │     partial unique: one primary domain per builder
  ├─ BuilderMembership(user FK, builder FK, role: builder_admin | marketing | sales)   unique(user, builder)
  └─ (settings) existing SiteSettings → OneToOne(Builder) + branding fields:
        logo, favicon, primary_color, secondary_color, font_heading, font_body,
        social links, notification_emails, from_email, tracking ids (GTM/GA4/Meta pixel)
```

Rather than adding a parallel `BuilderSettings`, the existing `SiteSettings` (phone, WhatsApp, address,
footer, SEO defaults) becomes the per-builder settings row — no duplicate model. Same for `HomePage`.

Existing models get a builder owner:

| Model | Change |
| --- | --- |
| `Project` | `builder` FK; `UniqueConstraint(builder, slug)` |
| `LandingPage` | `builder` FK, `project` FK (nullable: site-wide/custom pages), `template` (choice of registered templates), `is_published`; unique `(project, slug)` and `(builder, slug)` for project-less pages; model `clean()` rejects `project.builder != builder` |
| `LandingText/Image/Item` | unchanged (owned through their page) |
| `Enquiry` | `builder` FK (NOT NULL after backfill), `landing_page` FK, `source_domain`; `clean()`/`save()` enforce `project.builder == landing_page.builder == builder`; `lead_for` kept for M3M history |
| `SiteSettings`, `HomePage`, `BillionaireBlockPage` | `OneToOne(Builder)`; M3M keeps `pk=1` |
| `HeroBanner`, `Page`, `InnerPage`, `FAQ`, all `content` models | `builder` FK; slugs/keys unique per builder |

**Isolation approach:** explicit, not magic. A `TenantQuerySet.for_builder(builder)` on every owned model,
views always start from `request.builder`, forms receive the builder and validate every FK against it, and an
admin mixin scopes list/detail/FK choices/saves by the user's memberships (superusers see all). I recommend
**not** using an implicit thread-local default manager (hides bugs, breaks admin and migrations) and **not**
using PostgreSQL Row-Level Security in this phase: with one shared DB role and pooled connections it needs a
per-request `SET` inside every transaction, and the explicit layer plus cross-tenant tests gives the same
guarantee more transparently. RLS can be added later as defence in depth.

Django has no composite foreign keys, so "lead builder = project builder" is enforced in model validation and
`save()`, covered by tests, plus a `check_tenant_integrity` management command that reports any mismatch.

**Middleware** `tenants.middleware.TenantMiddleware`, placed right after `SecurityMiddleware` (before
sessions/CSRF so even error pages know the tenant): `request.get_host()` (Django validates it against
`ALLOWED_HOSTS`) → strip port, lower-case, IDNA-normalise → cached lookup of an *active, verified* domain of an
*active* builder → `request.builder`, `request.domain`. Unknown/inactive/unverified → plain 404 with no
builder data; inactive builder → 404 (or a configurable "site unavailable" 503). No default builder.
Cache: per-process with 60 s TTL and invalidation on `Domain`/`Builder` save.

**Local multi-domain testing:** Chrome, Edge and Firefox resolve `*.localhost` to 127.0.0.1 without editing
the hosts file. A dev-only command `manage.py add_local_domains` would create `m3m.localhost`, `ace.localhost`,
`xyz.localhost`, and explicit `localhost` / `127.0.0.1` rows for M3M, so `http://localhost:8000/` keeps working
— as data, not a code fallback.

**URLs:** existing paths stay exactly as they are on every builder's host. A project's first (default)
landing page stays at `/projects/<project-slug>`; additional landing pages at
`/projects/<project-slug>/<landing-slug>`.

**Templates:** M3M's templates stay untouched in place. A small template registry maps a `template` key to a
template path + slot module (today's `PAGES` dict, keyed per builder/template instead of per slug). Builder
theming via CSS custom properties fed from settings (`--brand-primary` …), applied only where a builder sets
them, so M3M's CSS is unaffected.

---

## 8. Phase plan (adapted to what the audit found)

| Phase | Work | Safety net |
| --- | --- | --- |
| 0 | Commit current uncommitted work as a checkpoint; run `backup.sh`; copy `db.sqlite3` to a dated, read-only file and record its SHA-256 | Original SQLite never written again |
| 2 | PostgreSQL: new database `m3m_platform` (the existing `m3m` PG DB is left alone); `.env.example`, optional `docker-compose.yml` (named volume) for machines without native PG; `scripts/migrate_sqlite_to_postgres` (dumpdata → loaddata → sequence reset → per-table counts + row checksums); run the full test suite and smoke-test pages against it; switch `.env` only after verification | Switching back = one line in `.env` |
| 3 | `tenants` app; owner FKs added nullable → data migration creates **M3M** and backfills every row → NOT NULL + per-builder unique constraints. Reconciliation report (expected: none) | Each migration small and reversible; tested on a copy first |
| 4 | `TenantMiddleware`, domain normalisation, cache, `ALLOWED_HOSTS` guidance, `add_local_domains` | Existing 70 tests must stay green with `localhost` mapped to M3M |
| 5 | `for_builder` querysets everywhere; scoped lead form/view/dedup; sitemap/robots/canonical per domain; cross-tenant tests | |
| 6 | M3M integration: context processor and views read builder settings; `SITE_URL` → primary domain; template registry with M3M templates unchanged; HTML snapshot comparison of key pages before/after | Byte-level diff of rendered M3M pages |
| 7 | Admin: Builder/Domain/Membership admin, scoped `ModelAdmin` mixin, roles (Super Admin / Builder Admin / Marketing / Sales), data-driven sidebar, leads by builder/project/landing page | |
| 8 | Full test run (SQLite + PostgreSQL), M3M end-to-end, sample ACE tenant | |
| 9 | Docs: README, LOCAL_SETUP, DATABASE_MIGRATION, MULTI_TENANT_ARCHITECTURE, ENVIRONMENT_SETUP | |

---

## 9. Decisions needed before Phase 2

1. **Checkpoint commit.** May I commit the current uncommitted work (ad tracking, `lead_for`, migrations
   0009/0010, SQLite docs) on a new branch before refactoring?
2. **Database direction.** Confirm PostgreSQL as primary despite yesterday's switch back to SQLite (and, if
   relevant, why it was switched). Native PostgreSQL 18 (already installed) for local dev, with Docker Compose
   as an optional alternative — OK?
3. **M3M's domains.** The code uses `www.m3mindia.com`; the brief says `m3mhome.in`. Which hostnames belong to
   M3M, and which is primary (canonical URLs and sitemap depend on it)?
4. **Admin location.** One central admin host (e.g. `admin.<your-company>.in`, recommended), or `/admin/` on
   every builder domain?
5. **Billionaire Block.** Keep it as an M3M custom page in the first pass (recommended), or turn it into a
   regular Project + landing page now?
6. **Next.js leftovers.** Remove `app/`, `components/`, `package.json`, `node_modules/`, `.next/` and replace
   the Next.js `AGENTS.md`? (Not required for the refactor; can wait.)
