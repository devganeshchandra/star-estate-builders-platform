"""Every existing record of the core app belongs to the first builder (M3M)."""

from django.db import migrations

from tenants.migration_helpers import assign_first_builder


class Migration(migrations.Migration):
    dependencies = [("core", "0014_builder_owner"), ("tenants", "0002_first_builder")]

    operations = [
        migrations.RunPython(
            assign_first_builder("core", "SiteSettings", "HomePage", "HeroBanner", "Page", "InnerPage", "FAQ"),
            migrations.RunPython.noop,
        )
    ]
