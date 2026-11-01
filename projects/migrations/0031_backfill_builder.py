"""Every existing record of the projects app belongs to the first builder (M3M).

Landing pages were linked to their project only by having the same slug (and a template file of that name).
That link becomes explicit: the page gets the project, is marked as the project's main page, and records its
design (template) under the same name. Builder-wide pages (website texts, Billionaire Block) keep no project.
"""

from django.db import migrations

from tenants.migration_helpers import assign_first_builder, first_builder


def link_landing_pages(apps, schema_editor):
    LandingPage = apps.get_model("projects", "LandingPage")
    Project = apps.get_model("projects", "Project")
    builder = first_builder(apps)
    for page in LandingPage.objects.filter(builder=builder):
        page.template = page.template or page.slug
        project = Project.objects.filter(builder=builder, slug=page.slug).first()
        if project is not None and page.project_id is None:
            page.project = project
            page.is_default = True
        page.save(update_fields=["template", "project", "is_default"])


class Migration(migrations.Migration):
    dependencies = [("projects", "0030_builder_owner"), ("tenants", "0002_first_builder")]

    operations = [
        migrations.RunPython(
            assign_first_builder("projects", "Project", "BillionaireBlockPage", "BillionaireItem", "LandingPage"),
            migrations.RunPython.noop,
        ),
        migrations.RunPython(link_landing_pages, migrations.RunPython.noop),
    ]
