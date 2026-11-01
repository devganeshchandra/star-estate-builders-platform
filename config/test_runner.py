from django.db.models.signals import post_migrate
from django.test.runner import DiscoverRunner


def add_test_domain(sender, using, **kwargs):
    from tenants.migration_helpers import FIRST_BUILDER_SLUG
    from tenants.models import Builder, Domain

    builder = Builder.objects.using(using).filter(slug=FIRST_BUILDER_SLUG).first()
    if builder is not None:
        Domain.objects.using(using).get_or_create(domain="testserver", defaults={"builder": builder, "is_verified": True})


class TenantTestRunner(DiscoverRunner):
    """Django's test client calls itself "testserver": that host serves the first builder (M3M) in every test
    database, the same way m3mhome.in does on the live site. Tests for other builders use their own domains.
    Added after migrations (and after every flush), so parallel test databases copied from it have it too."""

    def setup_databases(self, **kwargs):
        post_migrate.connect(add_test_domain, dispatch_uid="tenants-test-domain")
        return super().setup_databases(**kwargs)
