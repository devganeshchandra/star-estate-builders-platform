"""Everything a new builder's website needs before its team starts editing: settings, homepage text, the five menu
pages, the legal pages and the shared website texts (menu, footer, popup).

Starting texts are the first builder's, with its name replaced by the new builder's. Contact details (phone,
WhatsApp, address) start empty and no picture is copied: nothing of another builder's appears on the new site.
Safe to run again; it only adds what is missing.
"""

from django.db import transaction

from core.models import HomePage, InnerPage, Page, SiteSettings, rename_first_builder
from core.seed_pages import INNER_PAGES
from projects import landing
from projects.models import LandingPage

LEGAL_PAGES = [("Privacy", "privacy"), ("Disclaimer", "disclaimer"), ("Compliance", "compliance")]


@transaction.atomic
def provision(builder):
    site = SiteSettings.load(builder)
    HomePage.load(builder)

    for data in INNER_PAGES:
        values = {key: rename_first_builder(value, builder) for key, value in data.items() if key not in ("key", "banner")}
        InnerPage.objects.get_or_create(builder=builder, key=data["key"], defaults=values)

    for title, slug in LEGAL_PAGES:
        body = site.footer_disclaimer if slug == "disclaimer" else f"{title} information for {builder.name} will be published here."
        Page.objects.get_or_create(
            builder=builder, slug=slug, defaults={"title": title, "body": body, "is_published": slug == "disclaimer"}
        )

    texts = landing.builder_page(builder, landing.WEBSITE_TEXTS)
    if texts is None:
        module = landing.PAGES[landing.WEBSITE_TEXTS]
        texts = LandingPage.objects.create(
            builder=builder, slug=module.SLUG, name=module.NAME, template=module.SLUG
        )
        landing.fill_page(texts)
        for text in texts.texts.all():
            text.value = rename_first_builder(text.value, builder)
            text.save(update_fields=["value"])
        # The starting menu has the standard pages only; the builder's team adds its projects to the dropdown.
        texts.items.filter(list_key="project_menu").delete()
        texts.items.filter(list_key="menu", group="featured").delete()
    return builder
