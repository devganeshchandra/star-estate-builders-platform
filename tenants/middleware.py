from django.conf import settings
from django.http import HttpResponseNotFound

from tenants.models import normalize_domain
from tenants.resolver import resolve

NOT_FOUND = "Site not found."


class TenantMiddleware:
    """Works out which builder's website a request is for, from its host name, and sets
    `request.builder` and `request.domain`.

    The host has already passed ALLOWED_HOSTS (request.get_host() raises DisallowedHost otherwise). It must also be
    an active, verified domain of an active builder; anything else gets the same plain 404, so nothing reveals
    which builders or domains exist. There is deliberately no fallback builder.

    Exceptions: health checks (TENANT_EXEMPT_PATHS) need no builder, and the admin also answers on
    PLATFORM_ADMIN_HOSTS (e.g. admin.localhost), where `request.builder` is None: admin data is scoped by the
    user's builder memberships, never by the host.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.builder = None
        request.domain = None
        host = normalize_domain(request.get_host())
        path = request.path_info

        if path in settings.TENANT_EXEMPT_PATHS:
            return self.get_response(request)

        domain = resolve(host)
        if domain is not None:
            request.domain = domain
            request.builder = domain.builder
        elif not (host in settings.PLATFORM_ADMIN_HOSTS and path.startswith("/admin/")):
            return HttpResponseNotFound(NOT_FOUND, content_type="text/plain")
        return self.get_response(request)
