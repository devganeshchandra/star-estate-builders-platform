"""Host name → Domain (with its Builder), cached briefly per process.

Admin edits clear this process's entry at once (tenants/signals.py); other Gunicorn workers pick a change up
within TENANT_CACHE_SECONDS. Unknown host names are cached too, so junk Host headers cannot hammer the database.
"""

from django.conf import settings
from django.core.cache import cache

from tenants.models import Domain, normalize_domain

_MISSING = "missing"


def cache_key(host):
    return f"tenants:domain:{host}"


def resolve(host):
    """The servable Domain for this host (active, verified, of an active builder), or None."""
    host = normalize_domain(host)
    if not host:
        return None
    key = cache_key(host)
    domain = cache.get(key)
    if domain is None:
        domain = Domain.objects.select_related("builder").filter(domain=host).first() or _MISSING
        cache.set(key, domain, settings.TENANT_CACHE_SECONDS)
    if domain == _MISSING or not domain.is_servable:
        return None
    return domain


def forget(*hosts):
    cache.delete_many([cache_key(host) for host in hosts if host])
