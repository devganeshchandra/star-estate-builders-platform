"""Who may see and change which builder's data in the admin.

A superuser sees every builder. Everyone else sees only builders they have an active membership of, and only the
areas their role there allows:

    Builder admin       content, settings and leads of that builder
    Marketing manager   content (projects, landing pages, pages, articles, pictures)
    Sales               leads assigned to them

On top of this, Django's model permissions still apply (each role has a group with the matching permissions,
kept in step by tenants/signals.py), so a role can never do more than its group allows.
"""

from django.db.models import Q

from tenants.models import Builder, BuilderMembership

CONTENT, SETTINGS, LEADS = "content", "settings", "leads"
Role = BuilderMembership.Role
ROLE_AREAS = {
    Role.BUILDER_ADMIN: {CONTENT, SETTINGS, LEADS},
    Role.MARKETING: {CONTENT},
    Role.SALES: {LEADS},
}
# The Django group holding each role's model permissions (tenants/migrations/0003_role_groups.py).
ROLE_GROUPS = {
    Role.BUILDER_ADMIN: "Builder admins",
    Role.MARKETING: "Marketing managers",
    Role.SALES: "Sales",
}


def area_of(model):
    return getattr(model, "tenant_area", CONTENT)


def _memberships(user, area):
    roles = [role for role, areas in ROLE_AREAS.items() if area in areas]
    return BuilderMembership.objects.filter(user=user, is_active=True, role__in=roles, builder__is_active=True)


def builders_for(user, area):
    """The builders whose `area` this user may work on."""
    if not (user.is_authenticated and user.is_active and user.is_staff):
        return Builder.objects.none()
    if user.is_superuser:
        return Builder.objects.all()
    return Builder.objects.filter(pk__in=_memberships(user, area).values("builder"))


def scope(queryset, user):
    """Only the rows of `queryset` this user may see."""
    if user.is_superuser:
        return queryset
    model = queryset.model
    area = area_of(model)
    queryset = queryset.for_builders(builders_for(user, area))
    if area == LEADS:
        # Sales see their own leads; a builder admin sees all of that builder's leads.
        admin_of = _memberships(user, area).filter(role=Role.BUILDER_ADMIN).values("builder")
        queryset = queryset.filter(Q(builder__in=admin_of) | Q(assigned_to=user))
    return queryset


def may_access(user, obj):
    return scope(type(obj)._default_manager.filter(pk=obj.pk), user).exists()
