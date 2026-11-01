from django.conf import settings

from core.models import Page, SiteSettings
from projects import landing
from projects.landing_pages import site as site_texts
from projects.models import Project

# Header menu for a builder whose "Website texts" page is missing: the standard pages only.
FALLBACK_MENU = [item for item in site_texts.ITEMS["menu"] if not item["group"] == "featured"]


def _menu(lists, key):
    """A menu list from “Website texts” in the admin, or the standard pages if that page is missing."""
    if lists is None:
        return FALLBACK_MENU if key == "menu" else []
    return [{"title": i.title, "subtitle": i.subtitle, "link": i.link, "group": i.group} for i in lists.get(key, [])]


def site_url(request):
    """The builder's main address, for canonical links, sharing tags and search-engine data. Falls back to the
    address the visitor used when the builder has no primary domain yet."""
    primary = request.builder.primary_domain if getattr(request, "builder", None) else None
    if primary is None:
        return f"{request.scheme}://{request.get_host()}"
    return f"{settings.SITE_SCHEME}://{primary.domain}"


def site(request):
    builder = getattr(request, "builder", None)
    if builder is None:  # The admin on a platform-only host name: no builder website here.
        return {"builder": None}
    # The header menu, its Projects dropdown and the shared texts (st.<key>) are edited in the admin
    # under “Website texts” (projects/landing_pages/site.py).
    texts = landing.context(landing.builder_page(builder, landing.WEBSITE_TEXTS))
    lists = texts["lists"] if texts else None
    path = request.path
    navigation = [
        {
            "label": item["title"],
            "href": item["link"],
            "featured": item["group"] == "featured",
            "dropdown": item["group"] == "dropdown",
            "active": path == item["link"] or path.startswith(item["link"].rstrip("/") + "/"),
        }
        for item in _menu(lists, "menu")
    ]
    published = set(Project.objects.for_builder(builder).published().values_list("slug", flat=True))
    children = [
        {"label": item["title"], "note": item["subtitle"], "href": item["link"]}
        for item in _menu(lists, "project_menu")
        if not item["link"].startswith("/projects/") or item["link"].rstrip("/").rsplit("/", 1)[-1] in published
    ]
    for item in navigation:
        if item["dropdown"]:
            item["children"] = children
    return {
        "builder": builder,
        "site": SiteSettings.load(builder),
        "st": texts["t"] if texts else {key: value for _, key, _, value in site_texts.TEXTS},
        "navigation": navigation,
        # Footer links to the legal pages, only once each is published.
        "legal_pages": Page.objects.for_builder(builder).filter(is_published=True).order_by("slug"),
        "site_url": site_url(request),
    }
