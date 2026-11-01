"""Every existing record of the content app belongs to the first builder (M3M)."""

from django.db import migrations

from tenants.migration_helpers import assign_first_builder


class Migration(migrations.Migration):
    dependencies = [("content", "0005_builder_owner"), ("tenants", "0002_first_builder")]

    operations = [
        migrations.RunPython(
            assign_first_builder(
                "content", "JourneyPrinciple", "JourneyStat", "Milestone", "Publication", "PressItem", "MediaImage",
                "Video", "Insight",
            ),
            migrations.RunPython.noop,
        )
    ]
