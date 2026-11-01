"""Custom landing pages whose every text, image and list is edited in the admin.

Each page design (template) has a module in projects/landing_pages/ describing its content slots and their
starting content, and a template file templates/projects/landing/<design>.html (Billionaire Block and the
shared website texts have their own templates). Any builder can use any design: a LandingPage row records its
builder, its project and its design, and fill_page() gives a new page the design's starting content to edit.
context() hands a page's content to its template as:

    t.<key>              a text; render with |em to turn *stars* into italics
    imgs.<key>.image     a single picture, with imgs.<key>.alt; render with |src:<width>
    lists.<key>          the published items of a list, in order
"""

import copy
from pathlib import Path

from django.apps import apps as django_apps
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage

from projects.landing_pages import billionaire, cullinan, jacob, site, trump

PAGES = {module.SLUG: module for module in (jacob, cullinan, trump, billionaire, site)}
# Designs for a project's landing page (the other two are builder-wide pages with their own views).
PROJECT_TEMPLATES = {key: module for key, module in PAGES.items() if key not in (billionaire.SLUG, site.SLUG)}
BILLIONAIRE = billionaire.SLUG
WEBSITE_TEXTS = site.SLUG


def template_choices():
    return [(key, module.NAME) for key, module in PROJECT_TEMPLATES.items()]


def list_choices(template=None):
    """(key, name) of the lists of one design, or of every design."""
    modules = [PAGES[template]] if template in PAGES else PAGES.values()
    choices = {}
    for module in modules:
        for key, (name, _help) in module.LISTS.items():
            choices.setdefault(key, name)
    return sorted(choices.items(), key=lambda choice: choice[1])


def list_help(template):
    module = PAGES.get(template)
    return [(name, help_text) for name, help_text in module.LISTS.values()] if module else []


def _copy_static(module, filename, folder=None):
    """Copy a starting image from static/ into the media folder, where the admin can replace it."""
    if not filename:
        return ""
    name = f"{folder or 'landing/' + module.SLUG}/{Path(filename).name}"
    if not default_storage.exists(name):
        with open(Path(settings.BASE_DIR) / "static" / module.STATIC_DIR / filename, "rb") as source:
            name = default_storage.save(name, File(source))
    return name


def seed(apps=None):
    """Create any missing page, text and image. Lists are filled only when their page is new,
    so items the content team deleted do not come back. Never overwrites edited content.

    Used by the migrations written before the site served several builders (they created the first builder's
    pages); new pages are created in the admin and filled by fill_page()."""
    get_model = (apps or django_apps).get_model
    LandingPage = get_model("projects", "LandingPage")
    LandingText = get_model("projects", "LandingText")
    LandingImage = get_model("projects", "LandingImage")
    LandingItem = get_model("projects", "LandingItem")

    for module in PAGES.values():
        seo = dict(module.SEO)
        share_image = _copy_static(module, seo.pop("share_image", ""))
        page, created = LandingPage.objects.get_or_create(
            slug=module.SLUG, defaults={"name": module.NAME, "share_image": share_image, **seo}
        )
        for order, (section, key, label, value) in enumerate(module.TEXTS):
            text, new = LandingText.objects.get_or_create(
                page=page, key=key, defaults={"section": section, "label": label, "value": value, "order": order}
            )
            if not new:  # Sections, labels and order describe the template, so they follow the code.
                LandingText.objects.filter(pk=text.pk).update(section=section, label=label, order=order)
        for order, (section, key, label, filename, alt) in enumerate(module.IMAGES):
            image, new = LandingImage.objects.get_or_create(
                page=page,
                key=key,
                defaults={
                    "section": section,
                    "label": label,
                    "image": _copy_static(module, filename),
                    "alt": alt,
                    "order": order,
                },
            )
            if not new:
                LandingImage.objects.filter(pk=image.pk).update(section=section, label=label, order=order)
        if created:
            for list_key, items in module.ITEMS.items():
                for order, item in enumerate(items):
                    item = dict(item)
                    item["image"] = _copy_static(module, item.get("image", ""))
                    LandingItem.objects.create(page=page, list_key=list_key, order=order, **item)


def add_lists(apps, slug, keys):
    """Fill lists added to an existing page with their starting items, unless the list has items already."""
    LandingPage = apps.get_model("projects", "LandingPage")
    LandingItem = apps.get_model("projects", "LandingItem")
    page = LandingPage.objects.filter(slug=slug).first()
    if page is None:
        return
    module = PAGES[slug]
    for list_key in keys:
        if LandingItem.objects.filter(page=page, list_key=list_key).exists():
            continue
        for order, item in enumerate(module.ITEMS[list_key]):
            item = dict(item)
            item["image"] = _copy_static(module, item.get("image", ""))
            LandingItem.objects.create(page=page, list_key=list_key, order=order, **item)


def replace_texts(apps, slug, changes):
    """Swap starting texts for new ones, leaving any text the content team has edited as it is."""
    LandingText = apps.get_model("projects", "LandingText")
    for key, old, new in changes:
        LandingText.objects.filter(page__slug=slug, key=key, value=old).update(value=new)


def fill_page(page):
    """Give a new landing page its design's starting texts, pictures and lists. Pictures are copied into the
    builder's own media folder. Slots the page already has are left as they are."""
    from projects.models import LandingImage, LandingItem, LandingText

    module = PAGES.get(page.template)
    if module is None:
        return
    folder = f"builders/{page.builder.slug}/landing/{module.SLUG}"
    for order, (section, key, label, value) in enumerate(module.TEXTS):
        LandingText.objects.get_or_create(
            page=page, key=key, defaults={"section": section, "label": label, "value": value, "order": order}
        )
    for order, (section, key, label, filename, alt) in enumerate(module.IMAGES):
        LandingImage.objects.get_or_create(
            page=page,
            key=key,
            defaults={
                "section": section, "label": label, "image": _copy_static(module, filename, folder), "alt": alt,
                "order": order,
            },
        )
    if not page.items.exists():
        for list_key, items in module.ITEMS.items():
            for order, item in enumerate(items):
                item = dict(item)
                item["image"] = _copy_static(module, item.get("image", ""), folder)
                LandingItem.objects.create(page=page, list_key=list_key, order=order, **item)


def link_projects(builder):
    """A project's own landing page used to be found by sharing the project's slug. Make that link explicit for
    pages that do not have a project yet (e.g. after loading starting content on a new database)."""
    from projects.models import LandingPage, Project

    for page in LandingPage.objects.for_builder(builder).filter(project__isnull=True, template__in=PROJECT_TEMPLATES):
        project = Project.objects.for_builder(builder).filter(slug=page.slug).first()
        if project is not None and not project.landing_pages.filter(is_default=True).exists():
            page.project, page.is_default = project, True
            page.save(update_fields=["project", "is_default", "updated_at"])


def builder_page(builder, template):
    """A builder-wide page (the shared website texts, Billionaire Block) of this builder, or None."""
    from projects.models import LandingPage

    return LandingPage.objects.for_builder(builder).filter(project__isnull=True, template=template).first()


def context(page, rera=""):
    """Template context for a landing page, or None when there is no page."""
    if page is None:
        return None

    def fill(value):
        return value.replace("{rera}", rera)

    lists = {}
    for item in page.items.filter(is_published=True):
        item.title, item.text = fill(item.title), fill(item.text)
        lists.setdefault(item.list_key, []).append(item)
    return {
        "landing": page,
        "t": {text.key: fill(text.value) for text in page.texts.all()},
        "imgs": {image.key: image for image in page.images.all()},
        "lists": lists,
    }


def with_page_contact(site, texts):
    """The site settings with this page's own phone and WhatsApp numbers, when it has them, so every
    call and WhatsApp link on the page (header, buttons, mobile bar, footer, search-engine data) uses them.
    A page's own number is not the toll-free line, so the footer calls it plain “Call”."""
    numbers = {key: texts.get(key, "").strip() for key in ("phone_display", "phone_dial", "whatsapp_number")}
    if not any(numbers.values()):
        return site
    site = copy.copy(site)
    for key, value in numbers.items():
        if value:
            setattr(site, key, value)
    if numbers["phone_dial"]:
        site.phone_international = numbers["phone_dial"]
        site.phone_label = "Call"
    return site
