"""
Add a builder with its domain(s) and starting pages; the same as adding it in the admin (Builders → Add).

    python manage.py create_builder "ACE" ace acehome.in www.acehome.in
    python manage.py create_builder "ACE" ace acehome.in --verified     # DNS and HTTPS already work

The first domain becomes the main (primary) one. Domains start unverified unless --verified is given.
"""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tenants.models import Builder, Domain
from tenants.provisioning import provision


class Command(BaseCommand):
    help = "Add a builder with its domains and starting pages."

    def add_arguments(self, parser):
        parser.add_argument("name")
        parser.add_argument("slug")
        parser.add_argument("domains", nargs="*")
        parser.add_argument("--verified", action="store_true")

    @transaction.atomic
    def handle(self, name, slug, domains, verified=False, **options):
        builder, created = Builder.objects.get_or_create(slug=slug, defaults={"name": name})
        if not created and builder.name != name:
            raise CommandError(f"Builder {slug} already exists, named {builder.name}.")
        has_primary = builder.domains.filter(is_primary=True).exists()
        for host in domains:
            domain = Domain(builder=builder, domain=host, is_verified=verified, is_primary=not has_primary)
            try:
                domain.full_clean()
            except ValidationError as error:
                raise CommandError(f"{host}: {'; '.join(error.messages)}") from error
            domain.save()
            has_primary = True
            self.stdout.write(f"  {domain.domain}{' (main)' if domain.is_primary else ''}")
        provision(builder)
        self.stdout.write(self.style.SUCCESS(f"{builder} is ready. Add its domains to DJANGO_ALLOWED_HOSTS."))
