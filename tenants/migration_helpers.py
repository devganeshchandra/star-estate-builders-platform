"""Shared steps for the migrations that made the site multi-builder.

Every record that existed before then belonged to the one website, M3M, which became the first builder
(tenants/migrations/0002_first_builder.py). Migrations must not import models, so they use these helpers with
the historical `apps`.
"""

FIRST_BUILDER_SLUG = "m3m"


def first_builder(apps):
    return apps.get_model("tenants", "Builder").objects.get(slug=FIRST_BUILDER_SLUG)


def assign_first_builder(app_label, *model_names):
    """A RunPython function giving every row without a builder to the first builder."""

    def forwards(apps, schema_editor):
        builder = first_builder(apps)
        for name in model_names:
            apps.get_model(app_label, name).objects.filter(builder__isnull=True).update(builder=builder)

    return forwards
