"""The first builder's logos and icon were static files in the templates; they become its branding settings,
so every builder's templates read the logo from its own settings. The files are copied, not moved."""

from django.db import migrations

from core.branding import apply_first_builder_branding
from tenants.migration_helpers import first_builder


def forwards(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    builder = first_builder(apps)
    row = SiteSettings.objects.filter(builder=builder).first()
    if row is not None:  # A new, empty database gets them from `seed_content`.
        apply_first_builder_branding(row, builder.slug)
        row.save(update_fields=["logo", "logo_light", "favicon"])


class Migration(migrations.Migration):
    dependencies = [("core", "0017_branding_validators")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
