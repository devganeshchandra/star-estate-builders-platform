from django.apps import AppConfig


class TenantsConfig(AppConfig):
    name = "tenants"
    verbose_name = "Builders & domains"

    def ready(self):
        from tenants import signals  # noqa: F401  (cache invalidation)
