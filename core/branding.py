"""The first builder's logos and icon, which were static files before branding became a per-builder setting."""

from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage

FIRST_BUILDER_BRANDING = {
    "logo": "images/logo/m3m-logo.png",
    "logo_light": "images/logo/logo_tranparent.webp",
    "favicon": "images/logo/favicon-96.png",
}


def apply_first_builder_branding(site_settings, builder_slug):
    """Fill empty logo / icon fields from the static files (copied into the builder's media folder)."""
    for field, static_path in FIRST_BUILDER_BRANDING.items():
        if getattr(site_settings, field):
            continue
        source = Path(settings.BASE_DIR) / "static" / static_path
        name = f"builders/{builder_slug}/branding/{source.name}"
        if not default_storage.exists(name):
            with source.open("rb") as handle:
                name = default_storage.save(name, File(handle))
        setattr(site_settings, field, name)
