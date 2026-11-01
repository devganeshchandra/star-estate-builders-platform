"""Every existing lead belongs to the first builder (M3M): it was the only website.

Only facts already on the lead are used: an ad landing-page lead gets its project's main landing page, and the
website address is taken from the page it was sent from. Nothing is guessed; leads without these stay empty.
"""

from urllib.parse import urlsplit

from django.db import migrations

from tenants.migration_helpers import assign_first_builder


def link_landing_pages_and_domains(apps, schema_editor):
    Enquiry = apps.get_model("leads", "Enquiry")
    LandingPage = apps.get_model("projects", "LandingPage")
    for enquiry in Enquiry.objects.all():
        changed = []
        if enquiry.source == "landing" and enquiry.project_id and enquiry.landing_page_id is None:
            page = LandingPage.objects.filter(project_id=enquiry.project_id, is_default=True).first()
            if page is not None:
                enquiry.landing_page = page
                changed.append("landing_page")
        if not enquiry.source_domain and enquiry.page_url:
            host = (urlsplit(enquiry.page_url).hostname or "").lower()
            if host:
                enquiry.source_domain = host[:253]
                changed.append("source_domain")
        if changed:
            enquiry.save(update_fields=changed)


class Migration(migrations.Migration):
    dependencies = [
        ("leads", "0011_builder_owner"),
        ("projects", "0031_backfill_builder"),
        ("tenants", "0002_first_builder"),
    ]

    operations = [
        migrations.RunPython(assign_first_builder("leads", "Enquiry"), migrations.RunPython.noop),
        migrations.RunPython(link_landing_pages_and_domains, migrations.RunPython.noop),
    ]
