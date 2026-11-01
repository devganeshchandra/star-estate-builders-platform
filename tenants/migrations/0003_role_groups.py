"""One group per builder role, holding that role's model permissions. A person's groups follow their builder
memberships automatically (tenants/signals.py); which builder's records they reach is decided per membership
(tenants/access.py). Re-running keeps the permissions complete when new models are added.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

CONTENT_APPS = ("core", "content", "projects")
LEADS = {
    "Builder admins": ["view_enquiry", "change_enquiry", "delete_enquiry"],
    "Marketing managers": [],
    "Sales": ["view_enquiry", "change_enquiry"],
}


def forwards(apps, schema_editor):
    for app_config in apps.get_app_configs():
        app_config.models_module = True
        create_permissions(app_config, apps=apps, verbosity=0)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    current = [model._meta.model_name for model in apps.get_models() if model._meta.app_label in CONTENT_APPS]
    content = Permission.objects.filter(content_type__app_label__in=CONTENT_APPS, content_type__model__in=current)
    for name, lead_codenames in LEADS.items():
        group, _ = Group.objects.get_or_create(name=name)
        leads = Permission.objects.filter(content_type__app_label="leads", codename__in=lead_codenames)
        group.permissions.set([*(content if name != "Sales" else []), *leads])


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0002_first_builder"),
        ("core", "0018_first_builder_branding"),
        ("content", "0007_builder_required"),
        ("projects", "0032_builder_required"),
        ("leads", "0013_builder_required"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
