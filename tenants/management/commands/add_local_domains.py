"""
Development only: serve builders on *.localhost names, which browsers resolve to this machine by themselves.

    python manage.py add_local_domains                 # localhost, 127.0.0.1, m3m.localhost → M3M
                                                       # <slug>.localhost → every other builder
    python manage.py add_local_domains --demo          # also creates sample builders ACE and XYZ

Then open http://m3m.localhost:8000, http://ace.localhost:8000 … (DJANGO_ALLOWED_HOSTS must include .localhost).
Refuses to run with DJANGO_DEBUG off, so these names never reach a live database.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tenants.migration_helpers import FIRST_BUILDER_SLUG
from tenants.models import Builder, Domain
from tenants.provisioning import provision

DEMO_BUILDERS = [("ACE", "ace"), ("XYZ", "xyz")]


class Command(BaseCommand):
    help = "Map localhost names to builders for local development."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Also create the sample builders ACE and XYZ.")

    def handle(self, *args, demo=False, **options):
        if not settings.DEBUG:
            raise CommandError("Local domains are for development only (DJANGO_DEBUG is off).")
        if demo:
            for name, slug in DEMO_BUILDERS:
                builder, created = Builder.objects.get_or_create(slug=slug, defaults={"name": name})
                provision(builder)
                if created:
                    self.stdout.write(f"Created sample builder {name}")

        first = Builder.objects.get(slug=FIRST_BUILDER_SLUG)
        names = [(host, first) for host in ("localhost", "127.0.0.1")]
        names += [(f"{builder.slug}.localhost", builder) for builder in Builder.objects.all()]
        for host, builder in names:
            domain, created = Domain.objects.get_or_create(
                domain=host, defaults={"builder": builder, "is_verified": True}
            )
            if domain.builder_id != builder.pk:
                self.stderr.write(f"{host} already belongs to {domain.builder}; left as it is.")
                continue
            self.stdout.write(f"  http://{host}:8000/  →  {builder}{'' if created else ' (already set)'}")
