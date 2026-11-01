"""Builders (tenants), the domains that serve their websites, and the staff who work on each one.

Every builder-owned record points at a Builder, directly (`builder`) or through its parent (a landing page's
texts through the page, a project's gallery through the project). See docs/MULTI_TENANT_ARCHITECTURE.md.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def normalize_domain(value):
    """`Https://WWW.Example.in:8000/` → `www.example.in`: lower case, no scheme, port, path or trailing dot,
    international names in their ASCII (punycode) form. Returns "" for anything that is not a host name."""
    host = (value or "").strip().lower()
    host = re.sub(r"^[a-z][a-z0-9+.-]*://", "", host).split("/", 1)[0]
    if host.startswith("["):  # IPv6 literal: not used for builder sites
        return ""
    host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
    host = host.rstrip(".")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        return ""
    labels = host.split(".")
    if not host or len(host) > 253 or not all(_LABEL.match(label) for label in labels):
        return ""
    return host


class Builder(models.Model):
    """A real estate builder whose website(s) this platform runs: one tenant."""

    name = models.CharField(max_length=120, help_text="Shown on the website, e.g. “M3M”.")
    slug = models.SlugField(
        max_length=60, unique=True, help_text="Short internal name, e.g. “m3m”. Used in upload folders; do not change."
    )
    is_active = models.BooleanField(
        default=True, help_text="Untick to take every website of this builder offline (visitors see “not found”)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def primary_domain(self):
        return self.domains.filter(is_primary=True, is_active=True).first()


class Domain(models.Model):
    """A host name that serves one builder's website, e.g. m3mhome.in."""

    builder = models.ForeignKey(Builder, on_delete=models.PROTECT, related_name="domains")
    domain = models.CharField(
        max_length=253,
        unique=True,
        help_text="Host name only, e.g. “m3mhome.in” or “www.m3mhome.in” (no https://, no path).",
    )
    is_primary = models.BooleanField(
        default=False, help_text="The main address: used in links to the site, Google and the sitemap. One per builder."
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Tick once the domain's DNS points at this server and HTTPS works. Unverified domains are not served.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["builder", "-is_primary", "domain"]
        constraints = [
            models.UniqueConstraint(
                fields=["builder"], condition=models.Q(is_primary=True), name="tenants_one_primary_domain_per_builder"
            ),
            models.CheckConstraint(condition=models.Q(domain=Lower("domain")), name="tenants_domain_lowercase"),
        ]

    def __str__(self):
        return self.domain

    def clean(self):
        normalized = normalize_domain(self.domain)
        if not normalized:
            raise ValidationError({"domain": "Enter a host name such as “acehome.in”."})
        self.domain = normalized

    def save(self, *args, **kwargs):
        self.domain = normalize_domain(self.domain) or self.domain.strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_servable(self):
        return self.is_active and self.is_verified and self.builder.is_active


class BuilderMembership(models.Model):
    """Gives a staff user access to one builder in the admin, with a role deciding what they can do there."""

    class Role(models.TextChoices):
        BUILDER_ADMIN = "builder_admin", "Builder admin (everything for this builder)"
        MARKETING = "marketing", "Marketing manager (projects, landing pages, content)"
        SALES = "sales", "Sales (only the leads assigned to them)"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="builder_memberships")
    builder = models.ForeignKey(Builder, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["builder", "user"]
        constraints = [models.UniqueConstraint(fields=["user", "builder"], name="tenants_one_membership_per_builder")]

    def __str__(self):
        return f"{self.user} · {self.builder} · {self.get_role_display()}"
