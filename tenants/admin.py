from django.contrib import admin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, TabularInline

from tenants.models import Builder, BuilderMembership, Domain
from tenants.provisioning import provision


class SuperuserOnly:
    """Builders, domains and who works for which builder are managed by the platform's superusers only."""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request, *args):
        return request.user.is_active and request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False  # Deactivate instead: a builder's records are kept.


class DomainInline(SuperuserOnly, TabularInline):
    model = Domain
    extra = 0
    fields = ["domain", "is_primary", "is_verified", "is_active"]


class BuilderMembershipInline(SuperuserOnly, TabularInline):
    model = BuilderMembership
    extra = 0
    fields = ["builder", "role", "is_active"]
    verbose_name = "Builder access"
    verbose_name_plural = "Builder access (which builders this person works on, and their role)"


@admin.register(Builder)
class BuilderAdmin(SuperuserOnly, ModelAdmin):
    list_display = ["name", "slug", "websites", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "domains__domain"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [DomainInline]
    fields = ["name", "slug", "is_active"]

    def get_readonly_fields(self, request, obj=None):
        return ["slug"] if obj else []  # Upload folders are named after it.

    @admin.display(description="Domains")
    def websites(self, obj):
        rows = [
            (d.domain, " (main)" if d.is_primary else "", "" if d.is_verified else " · not verified")
            for d in obj.domains.all()
        ]
        return format_html_join(mark_safe("<br>"), "{}{}{}", rows) or "—"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        provision(obj)  # A new builder gets its starting settings, menu pages and website texts.


@admin.register(Domain)
class DomainAdmin(SuperuserOnly, ModelAdmin):
    list_display = ["domain", "builder", "is_primary", "is_verified", "is_active", "created_at"]
    list_filter = ["builder", "is_verified", "is_active"]
    list_editable = ["is_verified", "is_active"]
    search_fields = ["domain", "builder__name"]
    fieldsets = [
        (
            None,
            {
                "fields": ["builder", "domain", "is_primary", "is_active", "is_verified"],
                "description": (
                    "Before ticking “verified”: point the domain's DNS at the server, add it to DJANGO_ALLOWED_HOSTS "
                    "and the web server, and check that https://<domain>/healthz answers. Unverified domains are "
                    "not served."
                ),
            },
        )
    ]


@admin.register(BuilderMembership)
class BuilderMembershipAdmin(SuperuserOnly, ModelAdmin):
    list_display = ["user", "builder", "role", "is_active", "created_at"]
    list_filter = ["builder", "role", "is_active"]
    search_fields = ["user__username", "user__email", "builder__name"]
