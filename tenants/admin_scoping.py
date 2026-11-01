"""TenantScopedAdmin: limits an admin screen to the builders the user works for (tenants/access.py).

Applied to every builder-owned model's admin. It filters the list and every detail page (so changing the id in
the address of another builder's record gives "not found"), limits every builder / project / page choice to the
user's builders, rejects saving a record against a builder the user may not use, and checks that related records
(e.g. a press story's publication) belong to the same builder.
"""

from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError

from tenants import access
from tenants.models import Builder
from tenants.query import owner_of


def check_same_builder(obj):
    """Every builder-owned record this one points to must belong to the same builder."""
    owner = owner_of(obj)
    if owner is None:
        return
    for field in obj._meta.concrete_fields:
        if not field.is_relation or not hasattr(field.related_model, "tenant_path"):
            continue
        if field.name == obj.tenant_path.split("__")[0]:
            continue  # The ownership path itself.
        related = getattr(obj, field.name, None)
        if related is not None and owner_of(related) not in (None, owner):
            raise ValidationError({field.name: f"Choose one of {owner}'s own records."})


class TenantScopedAdmin(admin.ModelAdmin):
    def _area(self):
        return access.area_of(self.model)

    def _builders(self, request):
        return access.builders_for(request.user, self._area())

    # Which rows the user sees ------------------------------------------------------------------------------

    def get_queryset(self, request):
        return access.scope(super().get_queryset(request), request.user)

    def get_list_filter(self, request):
        """Related-record filters only offer records the user can see (never another builder's project names)."""
        filters = []
        for item in super().get_list_filter(request):
            if isinstance(item, str) and "__" not in item:
                field = self.model._meta.get_field(item)
                if field.is_relation:
                    item = (item, admin.RelatedOnlyFieldListFilter)
            filters.append(item)
        if request.user.is_superuser and "builder" in [f.name for f in self.model._meta.fields]:
            filters.insert(0, ("builder", admin.RelatedOnlyFieldListFilter))
        return filters

    # What the user may do ----------------------------------------------------------------------------------

    def has_module_permission(self, request):
        return super().has_module_permission(request) and self._builders(request).exists()

    def has_view_permission(self, request, obj=None):
        return self._allowed(request, obj, super().has_view_permission(request, obj))

    def has_change_permission(self, request, obj=None):
        return self._allowed(request, obj, super().has_change_permission(request, obj))

    def has_delete_permission(self, request, obj=None):
        return self._allowed(request, obj, super().has_delete_permission(request, obj))

    def has_add_permission(self, request, *args):
        return super().has_add_permission(request, *args) and self._builders(request).exists()

    def _allowed(self, request, obj, permitted):
        if not permitted or not self._builders(request).exists():
            return False
        return obj is None or access.may_access(request.user, obj)

    # Choices and saving ------------------------------------------------------------------------------------

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        related = db_field.related_model
        if related is Builder:
            kwargs["queryset"] = self._builders(request)
        elif hasattr(related, "tenant_path"):
            kwargs["queryset"] = related._default_manager.for_builders(self._builders(request))
        elif db_field.name == "assigned_to":
            from django.contrib.auth import get_user_model
            from django.db.models import Q

            kwargs["queryset"] = get_user_model().objects.filter(
                Q(is_superuser=True)
                | Q(builder_memberships__builder__in=self._builders(request), builder_memberships__is_active=True),
                is_active=True,
            ).distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        builders = list(self._builders(request)[:2])
        if len(builders) == 1 and "builder" in [f.name for f in self.model._meta.fields]:
            initial.setdefault("builder", builders[0].pk)
        return initial

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        builders = list(self._builders(request)[:2])

        class ScopedForm(form):
            def __init__(inner, *args, **kw):
                super().__init__(*args, **kw)
                field = inner.fields.get("builder")
                if field is not None and len(builders) == 1:  # Working on one builder: no need to choose it.
                    field.initial, field.disabled = builders[0].pk, True

            def _post_clean(inner):
                super()._post_clean()
                try:
                    check_same_builder(inner.instance)
                except ValidationError as error:
                    inner._update_errors(error)

        return ScopedForm

    def save_model(self, request, obj, form, change):
        owner = owner_of(obj)
        if owner is not None and not self._builders(request).filter(pk=owner.pk).exists():
            raise PermissionDenied("You do not work for this builder.")
        super().save_model(request, obj, form, change)

