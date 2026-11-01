"""M3M, the website this project started as, becomes the first builder; every existing record is given to it by
the next migration of each app. Its domains start unverified: tick “verified” in the admin once DNS points at
the server. Local development domains are added with `manage.py add_local_domains`, never here.
"""

from django.db import migrations

from tenants.migration_helpers import FIRST_BUILDER_SLUG

DOMAINS = [("m3mhome.in", True), ("www.m3mhome.in", False)]


def forwards(apps, schema_editor):
    Builder = apps.get_model("tenants", "Builder")
    Domain = apps.get_model("tenants", "Domain")
    builder, _ = Builder.objects.get_or_create(slug=FIRST_BUILDER_SLUG, defaults={"name": "M3M"})
    for domain, primary in DOMAINS:
        Domain.objects.get_or_create(domain=domain, defaults={"builder": builder, "is_primary": primary})


def backwards(apps, schema_editor):
    Builder = apps.get_model("tenants", "Builder")
    Domain = apps.get_model("tenants", "Domain")
    Domain.objects.filter(builder__slug=FIRST_BUILDER_SLUG).delete()
    Builder.objects.filter(slug=FIRST_BUILDER_SLUG).delete()


class Migration(migrations.Migration):
    dependencies = [("tenants", "0001_initial")]

    operations = [migrations.RunPython(forwards, backwards)]
