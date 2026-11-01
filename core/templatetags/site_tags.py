from django import template
from django.utils.html import format_html

from core.images import get_renditions

register = template.Library()


@register.simple_tag
def picture(field_file, sizes="100vw", alt="", css_class="", priority=False, fill=True):
    """Render an <img> with WebP srcset, like next/image did on the old site."""
    if not field_file:
        return ""
    candidates = [f"{url} {width}w" for url, width in get_renditions(field_file)]
    try:
        candidates.append(f"{field_file.url} {field_file.width}w")
    except Exception:
        pass
    classes = " ".join(filter(None, ["img-fill" if fill else "", css_class]))
    loading = "eager" if priority else "lazy"
    fetch_priority = "high" if priority else "auto"
    return format_html(
        '<img alt="{}" class="{}" src="{}" srcset="{}" sizes="{}" loading="{}" fetchpriority="{}" decoding="async">',
        alt,
        classes,
        field_file.url,
        ", ".join(candidates),
        sizes,
        loading,
        fetch_priority,
    )


@register.filter
def pad2(value):
    return f"{int(value):02d}"


@register.filter
def lt(value, other):
    return int(value) < int(other)


@register.inclusion_tag("partials/edit_this_page.html", takes_context=True)
def edit_this_page(context):
    """For logged-in staff only: a button that opens the admin screens editing the page on show
    (core/site_map.py), so the content team can go straight from a page to where it is edited."""
    request = context.get("request")
    if not request or not getattr(request.user, "is_staff", False):
        return {"show": False}
    from core.site_map import edits_for_path
    from tenants import access

    builder = getattr(request, "builder", None)
    if builder is None or not access.builders_for(request.user, access.CONTENT).filter(pk=builder.pk).exists():
        return {"show": False}
    name, edits = edits_for_path(request.builder, request.path)
    return {"show": True, "name": name, "edits": edits}
