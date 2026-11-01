"""A builder's website, page by page, and the admin screens that edit each part of it.

One map drives the admin home page (“Website map”) and the “Edit this page” button that staff see on the live
site, so both always agree on where each thing is edited. The map is built from the builder's own data: its
menu pages, its landing pages and its projects.
"""

from django.conf import settings
from django.urls import reverse

from tenants import access


def _changelist(model_name, query=""):
    app = {
        "enquiry": "leads",
        "project": "projects", "landingpage": "projects", "landingitem": "projects", "billionaireblockpage": "projects",
        "homepage": "core", "innerpage": "core", "herobanner": "core", "page": "core", "faq": "core",
        "sitesettings": "core", "user": "auth", "group": "auth",
    }.get(model_name, "content")
    return reverse(f"admin:{app}_{model_name}_changelist") + (f"?{query}" if query else "")


def _change(obj):
    if obj is None:
        return ""
    opts = obj._meta
    return reverse(f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk])


def _edit(label, href, hint=""):
    return {"label": label, "href": href, "hint": hint}


def site_map(builder, base_url=""):
    """Groups of pages: {title, intro, pages: [{name, url, note, edits: [{label, href, hint}]}]}.
    `base_url` is put in front of page addresses (another builder's site is on another domain)."""
    from core.models import HomePage, InnerPage, SiteSettings
    from projects import landing
    from projects.models import BillionaireBlockPage, LandingPage, Project

    inner = {page.key: _change(page) for page in InnerPage.objects.for_builder(builder)}
    texts = _change(landing.builder_page(builder, landing.WEBSITE_TEXTS))
    shared = _edit("Buttons & small headings", texts, "Website texts: the headings and buttons on this page")
    settings_url = _change(SiteSettings.objects.for_builder(builder).first()) or _changelist("sitesettings")
    homepage_url = _change(HomePage.objects.for_builder(builder).first()) or _changelist("homepage")
    billionaire = BillionaireBlockPage.objects.for_builder(builder).first()

    def page(name, url, note, edits):
        return {"name": name, "url": base_url + url, "note": note, "edits": [e for e in edits if e["href"]]}

    home_edits = [
        _edit("Homepage texts", homepage_url, "Banner words and each section’s heading and intro"),
        _edit("Banner pictures", _changelist("herobanner"), "The rotating pictures at the top"),
        _edit("Projects shown", _changelist("project", "is_featured__exact=1"), "Tick “Featured” on a project to show it"),
    ]
    if billionaire:
        home_edits.append(_edit("Billionaire Block band", _change(billionaire), "Homepage teaser section"))
    home_edits += [
        _edit("Journey figures", _changelist("journeystat"), "The numbers in “Our Journey”"),
        _edit("News on the homepage", _changelist("pressitem"), "Press stories"),
        shared,
    ]
    main = [
        page("Homepage", "/", "The banner, every section heading and the projects shown.", home_edits),
        page("Projects", "/projects", "Every project, grouped by stage.", [
            _edit("Page banner & texts", inner.get(InnerPage.Key.PROJECTS, "")),
            _edit("Projects", _changelist("project"), "Add, remove or reorder projects; set each one’s stage"),
            shared,
        ]),
        page("Our Journey", "/our-journey", "The builder’s story, values and milestones.", [
            _edit("Page banner & texts", inner.get(InnerPage.Key.JOURNEY, "")),
            _edit("Values", _changelist("journeyprinciple")),
            _edit("Figures", _changelist("journeystat")),
            _edit("Milestones", _changelist("milestone")),
            shared,
        ]),
        page("Media Centre", "/media-centre", "Pictures, films and press coverage.", [
            _edit("Page banner & texts", inner.get(InnerPage.Key.MEDIA, "")),
            _edit("Pictures", _changelist("mediaimage")),
            _edit("Films", _changelist("video")),
            _edit("Press stories", _changelist("pressitem")),
            _edit("Publication logos", _changelist("publication")),
            shared,
        ]),
        page("Insights", "/insights", "Articles and guides.", [
            _edit("Page banner & texts", inner.get(InnerPage.Key.INSIGHTS, "")),
            _edit("Articles", _changelist("insight"), "Write, edit or remove articles"),
            shared,
        ]),
        page("Contact", "/contact", "Phone, address, map, form and questions.", [
            _edit("Page banner & texts", inner.get(InnerPage.Key.CONTACT, "")),
            _edit("Phone, email, address & map", settings_url),
            _edit("Questions & answers", _changelist("faq")),
            shared,
        ]),
        page("Legal pages", "/disclaimer", "Disclaimer, privacy policy and other text pages.", [
            _edit("Legal pages", _changelist("page"), "Add a page, then publish it to show it in the footer"),
        ]),
    ]

    landing_pages = []
    for lp in LandingPage.objects.for_builder(builder).filter(project__isnull=False).select_related("project"):
        landing_pages.append(page(lp.name, lp.get_absolute_url(), f"Ad landing page · {lp.project.location}", [
            _edit("All page content", _change(lp),
                  "Every text, picture and list, section by section, including its phone, WhatsApp and RERA block"),
            _edit("Project name, RERA no. & card", _change(lp.project), "Also used on the Projects page"),
            _edit("Enquiries from this page", _changelist("enquiry", f"landing_page__id__exact={lp.pk}")),
        ]))
    if billionaire:
        landing_pages.append(page("Billionaire Block", "/billionaire-block", "Sector 111, Gurugram · ELIE SAAB", [
            _edit("Banner, viewing form, brochure & RERA", _change(billionaire),
                  "The top of the page, the private viewing form, residence choices and the footer"),
            _edit("All other page content", _change(landing.builder_page(builder, landing.BILLIONAIRE)),
                  "Every other text, picture and list, section by section"),
            _edit("Enquiries from this page", _changelist("enquiry", "source__exact=billionaire")),
        ]))

    standard = [
        page(project.name, project.get_absolute_url(), "Standard project page", [
            _edit("Project page", _change(project), "Name, texts, highlights, floor plans and gallery"),
            _edit("Enquiries", _changelist("enquiry", f"project__id__exact={project.pk}")),
        ])
        for project in Project.objects.for_builder(builder).exclude(landing_pages__is_default=True).order_by("order", "name")
    ]

    everywhere = [
        page("Header menu & shared texts", "/", "The menu, footer, enquiry popup and small headings on every page.", [
            _edit("Menu, footer & popup texts", texts, "Lists tab: the menu and Projects dropdown"),
        ]),
        page("Phone, WhatsApp, address, logo & footer", "/contact",
             "Used on every page except the ad landing pages, which have their own numbers.", [
                 _edit("Contact & site settings", settings_url, "Also the logo, colours, fonts and marketing tags"),
             ]),
    ]

    return [
        {"title": "Main website pages", "intro": "The pages in the website menu.", "pages": main},
        {"title": "Project landing pages", "intro": "The premium project pages used in advertising.", "pages": landing_pages},
        {"title": "Standard project pages", "intro": "Projects without their own landing page.", "pages": standard},
        {"title": "On every page", "intro": "Parts shared by the whole website.", "pages": everywhere},
    ]


def edits_for_path(builder, path):
    """The admin screens that edit the page at `path`, for the “Edit this page” button on the site."""
    from content.models import Insight
    from core.models import Page

    path = "/" + path.strip("/") if path != "/" else "/"
    # An article or a legal page opens itself; every other page opens its entry in the map.
    if path.startswith("/insights/"):
        insight = Insight.objects.for_builder(builder).filter(slug=path.rsplit("/", 1)[-1]).first()
        if insight:
            return insight.title, [_edit("This article", _change(insight)), _edit("All articles", _changelist("insight"))]
    legal = Page.objects.for_builder(builder).filter(slug=path.lstrip("/")).first()
    if legal:
        return legal.title, [_edit("This page", _change(legal)), _edit("All legal pages", _changelist("page"))]
    for group in site_map(builder):
        for page in group["pages"]:
            if page["url"] == path and group["title"] != "On every page":
                return page["name"], page["edits"]
    return None, []


def _base_url(request, builder):
    """Page links in the map open on the builder's own website: here if this is it, else its main domain."""
    if getattr(request, "builder", None) == builder:
        return ""
    primary = builder.primary_domain
    return f"{settings.SITE_SCHEME}://{primary.domain}" if primary else ""


def dashboard(request, context):
    """The admin home page: the chosen builder's website map, and the enquiries waiting for a call."""
    from leads.models import Enquiry

    builders = list(access.builders_for(request.user, access.CONTENT))
    chosen = request.GET.get("builder")
    builder = next((b for b in builders if b.slug == chosen), None)
    if builder is None:
        builder = getattr(request, "builder", None) if getattr(request, "builder", None) in builders else None
    builder = builder or (builders[0] if builders else None)

    waiting = access.scope(Enquiry.objects.all(), request.user).filter(status=Enquiry.Status.NEW)
    context.update(
        {
            "builder": builder,
            "builders": builders if len(builders) > 1 else [],
            "site_map": site_map(builder, _base_url(request, builder)) if builder else [],
            "new_enquiries": waiting.count(),
            "new_enquiries_url": _changelist("enquiry", f"status__exact={Enquiry.Status.NEW}"),
            "all_enquiries_url": _changelist("enquiry"),
        }
    )
    return context
