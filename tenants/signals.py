from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from tenants.models import Builder, BuilderMembership, Domain
from tenants.resolver import forget


@receiver(pre_save, sender=Domain)
def remember_old_name(sender, instance, **kwargs):
    if instance.pk:
        instance._old_domain = Domain.objects.filter(pk=instance.pk).values_list("domain", flat=True).first()


@receiver([post_save, post_delete], sender=Domain)
def domain_changed(sender, instance, **kwargs):
    forget(instance.domain, getattr(instance, "_old_domain", None))


@receiver(post_save, sender=Builder)
def builder_changed(sender, instance, **kwargs):
    forget(*instance.domains.values_list("domain", flat=True))


@receiver([post_save, post_delete], sender=BuilderMembership)
def membership_changed(sender, instance, **kwargs):
    """Keep the user's role groups (their model permissions) in step with their active memberships."""
    from django.contrib.auth.models import Group

    from tenants.access import ROLE_GROUPS

    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=instance.user_id).first()
    if user is None:  # The user is being deleted.
        return
    wanted = {
        ROLE_GROUPS[role] for role in user.builder_memberships.filter(is_active=True).values_list("role", flat=True)
    }
    groups = {group.name: group for group in Group.objects.filter(name__in=ROLE_GROUPS.values())}
    user.groups.remove(*[group for name, group in groups.items() if name not in wanted])
    user.groups.add(*[group for name, group in groups.items() if name in wanted])
