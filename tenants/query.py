"""Tenant ownership for models: querysets that filter by builder, and per-builder upload folders.

Every builder-owned model sets `tenant_path`, the lookup from the model to its Builder ("builder", or e.g.
"page__builder" for a landing page's texts). Queries are filtered explicitly with `.for_builder(builder)`;
there is no hidden default filter, so a missing filter is visible in code review and caught by the tests.
"""

from django.db import models
from django.utils.deconstruct import deconstructible


class TenantQuerySet(models.QuerySet):
    def for_builder(self, builder):
        if builder is None:
            return self.none()
        return self.filter(**{self.model.tenant_path: builder})

    def for_builders(self, builders):
        return self.filter(**{f"{self.model.tenant_path}__in": builders})


def owner_of(obj):
    """The Builder an object belongs to, following its tenant_path; None if not set yet."""
    for part in obj.tenant_path.split("__"):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


@deconstructible
class BuilderUploadTo:
    """upload_to: files go to builders/<builder slug>/<folder>/, so builders' files never share a folder or
    a file name. Files uploaded before multi-tenancy keep their original paths."""

    def __init__(self, folder):
        self.folder = folder.strip("/")

    def __call__(self, instance, filename):
        builder = owner_of(instance)
        prefix = f"builders/{builder.slug}/" if builder is not None else ""
        return f"{prefix}{self.folder}/{filename}"

    def __eq__(self, other):
        return isinstance(other, BuilderUploadTo) and other.folder == self.folder
