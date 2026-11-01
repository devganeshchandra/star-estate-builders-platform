"""
Report records whose builder does not match the records they point to, and leads that need a person to decide.

    python manage.py check_tenant_integrity

Changes nothing. Exits with an error when a cross-builder link is found (none should exist: they are rejected
when saved), so it can run after deployments and in monitoring.
"""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from leads.models import Enquiry
from tenants.query import owner_of


class Command(BaseCommand):
    help = "Check that every builder-owned record only points to records of the same builder."

    def handle(self, *args, **options):
        problems = 0
        for model in apps.get_models():
            if not hasattr(model, "tenant_path"):
                continue
            relations = [
                f for f in model._meta.concrete_fields
                if f.is_relation and hasattr(f.related_model, "tenant_path") and f.name != model.tenant_path.split("__")[0]
            ]
            if not relations:
                continue
            for obj in model._default_manager.select_related(*[f.name for f in relations]).iterator():
                owner = owner_of(obj)
                for field in relations:
                    related = getattr(obj, field.name)
                    if related is not None and owner_of(related) != owner:
                        problems += 1
                        self.stderr.write(f"{model._meta.label} {obj.pk}: {field.name} belongs to {owner_of(related)}, not {owner}")
        self.stdout.write(f"Cross-builder links: {problems}")

        # Not errors: leads that simply did not say which project or page they were about.
        no_project = Enquiry.objects.filter(project__isnull=True)
        landing_without_page = Enquiry.objects.filter(source=Enquiry.Source.LANDING, landing_page__isnull=True)
        self.stdout.write(f"Leads without a project (general enquiries): {no_project.count()}")
        self.stdout.write(f"Ad landing-page leads without a landing page, to review by hand: {landing_without_page.count()}")
        for enquiry in landing_without_page[:50]:
            self.stdout.write(f"  lead {enquiry.pk} · {enquiry.builder} · project {enquiry.project or '—'} · {enquiry.page_url}")
        if problems:
            raise CommandError(f"{problems} cross-builder link(s) found.")
