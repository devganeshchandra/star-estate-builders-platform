"""
Django settings for the M3M India website.

Everything environment-specific is read from environment variables (or a
local `.env` file). See `.env.example` for the full list.
"""

import os
from pathlib import Path

from django.templatetags.static import static
from django.urls import reverse_lazy
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-local-development-key-change-me" if DEBUG else "",
)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")

# Every builder domain must be listed here as well as in the admin (Builders & domains → Domains): this list is
# Django's first check of the Host header, the Domain table decides which builder answers. A leading dot allows
# sub-domains, e.g. ".localhost" for m3m.localhost and ace.localhost on a development machine.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Multi-builder hosting (tenants/middleware.py). Host names that serve only the admin, with no builder website,
# e.g. admin.yourcompany.in. The admin also works on every builder domain.
PLATFORM_ADMIN_HOSTS = env_list("PLATFORM_ADMIN_HOSTS", "admin.localhost")
# Paths answered without a builder (load balancer / uptime checks).
TENANT_EXEMPT_PATHS = {"/healthz"}
# How long each web process remembers which builder a host name belongs to; admin edits apply immediately in the
# process that saved them and within this many seconds everywhere else.
TENANT_CACHE_SECONDS = int(os.environ.get("TENANT_CACHE_SECONDS", "60"))
# Links in emails and canonical addresses use https unless this says otherwise (e.g. "http" on a laptop).
SITE_SCHEME = os.environ.get("SITE_SCHEME", "https")
PLATFORM_NAME = os.environ.get("PLATFORM_NAME", "Builder websites")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    # WhiteNoise serves static files in development too, with headers that stop
    # browsers reusing an old copy of the CSS/JS after an edit.
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "tenants",
    "core",
    "projects",
    "content",
    "leads",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Which builder's website this is, from the host name. After WhiteNoise (static files need no builder),
    # before everything that shows or saves builder data.
    "tenants.middleware.TenantMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: PostgreSQL, one database shared by every builder (DB_* settings in .env). DB_ENGINE=sqlite opens an
# SQLite file (db.sqlite3, or DB_PATH): the original file is kept for rolling back with the code from before the
# multi-builder change, never to be migrated in place. See docs/DATABASE_MIGRATION.md.
if os.environ.get("DB_ENGINE", "postgres").lower() in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "m3m"),
            "USER": os.environ.get("DB_USER", "m3m"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
            # Keep connections open between requests, and check one is alive before reusing it.
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "60")),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": 10,
                # "require" when the database is on another server (e.g. a managed cloud database).
                "sslmode": os.environ.get("DB_SSLMODE", "prefer"),
                "application_name": "m3m-website",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("DB_PATH") or BASE_DIR / "db.sqlite3",
            "OPTIONS": {
                # Two leads sent at the same moment: the second waits up to 20 seconds for its turn rather than
                # failing with "database is locked". IMMEDIATE takes the write lock at the start of a transaction,
                # so a waiting write never fails half-way.
                "timeout": 20,
                "transaction_mode": "IMMEDIATE",
                # WAL: pages keep loading while a lead is being saved. NORMAL is safe with WAL and much faster.
                "init_command": (
                    "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=20000;"
                    " PRAGMA cache_size=-20000; PRAGMA temp_store=MEMORY"
                ),
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "m3m",
    }
}

# Uploaded images larger than this are resized on save, and the site serves
# WebP renditions at these widths (similar to next/image).
IMAGE_MAX_UPLOAD_WIDTH = 2560
IMAGE_RENDITION_WIDTHS = (480, 828, 1200, 1920)

# Lead notifications. Each builder's own inbox is in its settings (admin); these comma-separated addresses get a
# copy of every builder's leads (e.g. the platform's operations team). Leave empty for none.
LEAD_NOTIFICATION_EMAILS = env_list("LEAD_NOTIFICATION_EMAILS")
LEAD_RATE_LIMIT_PER_HOUR = int(os.environ.get("LEAD_RATE_LIMIT_PER_HOUR", "20"))

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", f"{PLATFORM_NAME} <no-reply@localhost>")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    # Requests for host names outside ALLOWED_HOSTS are refused (400); scanners send many, so keep them quiet.
    "loggers": {"django.security.DisallowedHost": {"handlers": ["console"], "level": "ERROR", "propagate": False}},
}

UNFOLD = {
    "SITE_TITLE": f"{PLATFORM_NAME} admin",
    "SITE_HEADER": PLATFORM_NAME,
    "SITE_SUBHEADER": "Builders, websites & enquiries",
    "SITE_URL": "/",
    "SITE_SYMBOL": "apartment",
    "SITE_FAVICONS": [
        {"rel": "icon", "type": "image/png", "href": lambda request: static("images/logo/icon-512.png")},
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "COLORS": {
        "primary": {
            "50": "oklch(97% .012 85)",
            "100": "oklch(94% .03 85)",
            "200": "oklch(89% .06 83)",
            "300": "oklch(82% .09 80)",
            "400": "oklch(74% .11 78)",
            "500": "oklch(68% .12 76)",
            "600": "oklch(60% .115 74)",
            "700": "oklch(51% .1 72)",
            "800": "oklch(43% .08 70)",
            "900": "oklch(36% .065 68)",
            "950": "oklch(26% .05 66)",
        },
    },
    "DASHBOARD_CALLBACK": "core.site_map.dashboard",
    # The sidebar follows the website itself: its pages, then the landing pages, then shared parts.
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Start here",
                "items": [
                    {"title": "Website map (every page)", "icon": "map", "link": reverse_lazy("admin:index")},
                    {"title": "Enquiries", "icon": "inbox", "link": reverse_lazy("admin:leads_enquiry_changelist")},
                ],
            },
            {
                "title": "Main website pages",
                "items": [
                    {"title": "Homepage", "icon": "home", "link": reverse_lazy("admin:core_homepage_changelist")},
                    {"title": "Menu pages (Projects, Journey, Media…)", "icon": "web", "link": reverse_lazy("admin:core_innerpage_changelist")},
                    {"title": "Legal pages (disclaimer, privacy…)", "icon": "description", "link": reverse_lazy("admin:core_page_changelist")},
                ],
            },
            {
                "title": "Project landing pages",
                "items": [
                    {"title": "All landing pages (add one here)", "icon": "diamond", "link": reverse_lazy("admin:projects_landingpage_changelist")},
                    {"title": "Billionaire Block: banner & form", "icon": "workspace_premium", "link": reverse_lazy("admin:projects_billionaireblockpage_changelist")},
                ],
            },
            {
                "title": "Projects",
                "items": [
                    {"title": "All projects (cards & project pages)", "icon": "domain", "link": reverse_lazy("admin:projects_project_changelist")},
                    {"title": "Landing page list items (all)", "icon": "format_list_bulleted", "link": reverse_lazy("admin:projects_landingitem_changelist")},
                ],
            },
            {
                "title": "Content libraries",
                "items": [
                    {"title": "Homepage banner pictures", "icon": "photo_library", "link": reverse_lazy("admin:core_herobanner_changelist")},
                    {"title": "Journey values", "icon": "star", "link": reverse_lazy("admin:content_journeyprinciple_changelist")},
                    {"title": "Journey figures", "icon": "bar_chart", "link": reverse_lazy("admin:content_journeystat_changelist")},
                    {"title": "Journey milestones", "icon": "flag", "link": reverse_lazy("admin:content_milestone_changelist")},
                    {"title": "Press stories", "icon": "newspaper", "link": reverse_lazy("admin:content_pressitem_changelist")},
                    {"title": "Publication logos", "icon": "verified", "link": reverse_lazy("admin:content_publication_changelist")},
                    {"title": "Media pictures", "icon": "image", "link": reverse_lazy("admin:content_mediaimage_changelist")},
                    {"title": "Films", "icon": "smart_display", "link": reverse_lazy("admin:content_video_changelist")},
                    {"title": "Insight articles", "icon": "article", "link": reverse_lazy("admin:content_insight_changelist")},
                    {"title": "Contact page questions (FAQ)", "icon": "help", "link": reverse_lazy("admin:core_faq_changelist")},
                ],
            },
            {
                "title": "On every page",
                "items": [
                    {"title": "Menu, footer & popup texts", "icon": "menu", "link": lambda request: f"{reverse_lazy('admin:projects_landingpage_changelist')}?project__isnull=True"},
                    {"title": "Phone, address, logo & tags", "icon": "settings", "link": reverse_lazy("admin:core_sitesettings_changelist")},
                ],
            },
            {
                "title": "Builders (superusers)",
                "items": [
                    {"title": "Builders", "icon": "business", "link": reverse_lazy("admin:tenants_builder_changelist"), "permission": lambda request: request.user.is_superuser},
                    {"title": "Domains", "icon": "language", "link": reverse_lazy("admin:tenants_domain_changelist"), "permission": lambda request: request.user.is_superuser},
                    {"title": "Who works on which builder", "icon": "badge", "link": reverse_lazy("admin:tenants_buildermembership_changelist"), "permission": lambda request: request.user.is_superuser},
                ],
            },
            {
                "title": "Team",
                "items": [
                    {"title": "Users", "icon": "person", "link": reverse_lazy("admin:auth_user_changelist"), "permission": lambda request: request.user.is_superuser},
                    {"title": "Groups & permissions", "icon": "group", "link": reverse_lazy("admin:auth_group_changelist"), "permission": lambda request: request.user.is_superuser},
                ],
            },
        ],
    },
}
TEST_RUNNER = "config.test_runner.TenantTestRunner"
