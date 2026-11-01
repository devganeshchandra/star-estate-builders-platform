# Multi-builder architecture

One repository, one Django application, one shared PostgreSQL database, many domains. A **builder** is a
tenant. Each builder's data is kept apart by explicit ownership on every record, checked in the request
path, the forms, the models and the admin.

```
 m3mhome.in ─┐                        ┌─ request.builder = M3M ─► M3M's projects, pages, leads…
 acehome.in ─┼─► Nginx ─► Gunicorn ─► TenantMiddleware ─┤
 xyzhome.in ─┘   (unknown hosts       (Domain table)     └─ unknown / unverified / inactive ─► 404
                  dropped)                                                     │
                                            one PostgreSQL database ◄──────────┘
```

## Data model

| Model | Owned by | Notes |
| --- | --- | --- |
| `tenants.Builder` | — | `name`, `slug` (unique; names upload folders), `is_active` |
| `tenants.Domain` | builder | `domain` unique, stored normalised (lower case, no port/scheme, punycode); `is_primary` (one per builder, DB constraint), `is_verified`, `is_active` |
| `tenants.BuilderMembership` | builder | staff user + builder + role; unique per user and builder |
| `core.SiteSettings` | builder (one row each) | contact details, footer, SEO defaults, **lead inbox, logo, favicon, colours, fonts, social links, GTM / GA4 / Meta pixel** — the builder's settings |
| `core.HomePage` | builder (one row each) | homepage texts |
| `core.InnerPage` | builder | the five menu pages; `key` unique per builder |
| `core.Page`, `core.HeroBanner`, `core.FAQ` | builder | legal pages (`slug` unique per builder), banners, FAQs |
| `content.*` | builder | journey values/stats/milestones, publications (`name` unique per builder), press, media, videos, insights (`slug` unique per builder) |
| `projects.Project` | builder | **`slug` unique per builder**: `m3m + jacob` and `ace + jacob` both allowed |
| `projects.LandingPage` | builder (+ project) | `project`, `template` (design), `is_default` (the project's main page, one per project), `is_published`; slug unique per project (or per builder for builder-wide pages) |
| `LandingText / LandingImage / LandingItem` | through their page | every text, picture and list item on a landing page |
| `projects.BillionaireBlockPage` (+ items, residences, news) | builder | M3M's custom page; other builders simply have none |
| `leads.Enquiry` | builder | + `project`, `landing_page`, `source_domain`, UTM and click IDs, contact details, timestamps |

Every owned model declares `tenant_path` (`"builder"`, or `"page__builder"` / `"project__builder"` for child
records) and uses `TenantQuerySet` (`tenants/query.py`) with `.for_builder(builder)` and `.for_builders(...)`.
There is deliberately **no implicit default filter**: every query names its builder, so a missing filter is
visible in review and caught by the tests.

### Ownership rules enforced

- Database: every `builder` column is `NOT NULL` with `ON DELETE PROTECT` (a builder with data cannot be
  deleted; deactivate it instead); unique constraints are per builder / per project.
- Models: `LandingPage.save()` refuses a project of another builder; `Enquiry.save()` refuses a project,
  landing page or salesperson of another builder. Django has no composite foreign keys, so these checks live
  in the model and are covered by tests.
- Forms: the lead form takes the builder from the host (never from the posted data) and looks up the project
  and landing page within that builder only.
- Admin: `tenants/admin_scoping.py` filters lists and detail pages, limits every choice to the user's builders,
  rejects related records of another builder and refuses saves for a builder the user does not work for.
- Audit: `python manage.py check_tenant_integrity` reports any cross-builder link (expected: 0).

PostgreSQL Row-Level Security is not used: with one database login and pooled connections it would need a
per-request `SET` inside every transaction. The explicit layers above give the same isolation more
transparently; RLS can be added later as an extra layer.

## Domain → builder (middleware)

`tenants.middleware.TenantMiddleware` (right after WhiteNoise, so static files need no builder):

1. `request.get_host()` — Django first refuses hosts outside `ALLOWED_HOSTS` (HTTP 400).
2. Normalise the host (`normalize_domain`).
3. Look it up in `Domain` (cached per process for `TENANT_CACHE_SECONDS`, unknown hosts too; an admin edit
   clears the entry at once in that process).
4. Serve only an **active, verified** domain of an **active** builder: `request.builder`, `request.domain`.
5. Anything else → the same plain `404 Site not found.`, revealing nothing.

Exceptions: `/healthz` needs no builder; `/admin/` also answers on `PLATFORM_ADMIN_HOSTS`. The admin works on
every builder domain too: what a person sees there depends on their memberships, never on the host. No URL
parameter, cookie or form field can choose a builder.

Canonical links, sharing tags, JSON-LD and the sitemap use the builder's **primary domain**
(`SITE_SCHEME://<primary>`); the sitemap lists only that builder's pages.

## Roles

| Role | Can | Cannot |
| --- | --- | --- |
| Superuser | everything, every builder; builders, domains, memberships, users | — |
| Builder admin | all content, settings and leads of their builder(s) | other builders; builders/domains/users |
| Marketing manager | projects, landing pages, pages, articles, media, menus | settings (contact/branding/tags), leads |
| Sales | leads assigned to them (view, update status/notes) | content, unassigned leads |

A person can have different roles for different builders. Each role also has a Django group
(`Builder admins`, `Marketing managers`, `Sales`) holding its model permissions; groups follow the person's
memberships automatically. Staff without a membership see no builder data at all.

## Templates and branding

- The M3M design (templates and CSS) is shared. Builder-specific values come from `SiteSettings`: logo
  (`site.logo`, or the builder's name as a text wordmark), favicon, and — only when filled in — colours
  (`--ink`, `--champagne`) and Google fonts (`--font-display`, `--font-body`) through
  `templates/partials/brand_head.html`. Empty values leave the stylesheet exactly as it is, which is why M3M's
  pages are unchanged.
- Landing page **designs** are registered in `projects/landing.py` (`PAGES`); each has a slot module in
  `projects/landing_pages/` and a template `templates/projects/landing/<design>.html`. Any builder can use any
  design for any of its projects, and a project can have several landing pages (one per campaign).
- A completely different design for one builder or project = a new design module + template (below). No
  page-builder system is involved.

## Adding a new builder

In the admin (superuser): **Builders → Add builder** (name, slug), add its domains in the same form, save.
Or from the command line:

```bash
python manage.py create_builder "ACE" ace acehome.in www.acehome.in
```

Either way the builder gets its settings, homepage text, the five menu pages, legal pages and the shared
website texts (menu, footer, popup), with its own name and **empty** contact details — nothing of another
builder is copied. Then:

1. **Contact & site settings** (choose the builder): phone, WhatsApp, address, lead inbox, logo, favicon,
   colours, fonts, tags.
2. **Projects → Add**, then **Landing pages → Add** for each project (pick a design).
3. **Menu, footer & popup texts → Lists**: add the projects to the header's Projects dropdown.
4. **Menu pages**: upload the banner pictures.
5. **Who works on which builder**: give the builder's staff their role.
6. Go live: add the domains to `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS`, point DNS at the
   server, re-run `sudo ./scripts/install_server.sh <all domains>` for Nginx and HTTPS, check
   `https://<domain>/healthz`, then tick **verified** on the domain.

Locally: `python manage.py add_local_domains` maps `<slug>.localhost` to every builder.

## Adding a landing page design

1. `templates/projects/landing/<design>.html`, reading `t.<key>` (texts, `|em` for italics),
   `imgs.<key>` (pictures, `|src:<width>`) and `lists.<key>`.
2. `projects/landing_pages/<design>.py` with `SLUG`, `NAME`, `STATIC_DIR`, `SEO`, `TEXTS`, `IMAGES`, `LISTS`,
   `ITEMS` (copy an existing one), listed in `PAGES` in `projects/landing.py`.
3. It then appears in **Landing pages → Add → Design** for every builder. No migration is needed.

## Things kept for M3M compatibility

- `Enquiry.lead_for` (Jacob / Cullinan / Trump / Billionaire / Core) is M3M's earlier reporting field and is
  still filled for every lead; for other builders it says "Core". Use **builder / project / landing page** for
  reporting instead.
- The Billionaire Block page keeps its own models and route; only builders that have one show it.
- `seed_content` loads M3M's starter content (into the builder given with `--builder`, default `m3m`).

## Files and media

New uploads go to `media/builders/<builder slug>/<folder>/`, so builders never share a folder or a file name;
files uploaded before the change keep their paths. Everything under `/media/` is public (images, brochures),
as before: do not upload private documents. A brochure meant to be "unlocked" by a form is still reachable by
its address; serving such files through a checked view is a possible next step.
