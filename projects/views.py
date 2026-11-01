from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from core.models import InnerPage, SiteSettings
from core.views import inner_page
from projects import landing
from projects.models import BillionaireBlockPage, LandingPage, Project


@require_GET
def project_list(request):
    page = inner_page(request.builder, InnerPage.Key.PROJECTS)
    projects = list(Project.objects.for_builder(request.builder).published())
    texts = {
        Project.Status.DELIVERED: page.delivered_text,
        Project.Status.CURRENT: page.current_text,
        Project.Status.UPCOMING: page.upcoming_text,
    }
    collections = []
    # Shown in this order: what you can own now first, then what's next, then the track record.
    for index, status in enumerate((Project.Status.CURRENT, Project.Status.UPCOMING, Project.Status.DELIVERED), 1):
        name, subtitle = Project.COLLECTIONS[status]
        collections.append(
            {
                "key": status.value,
                "index": index,
                "name": name,
                "subtitle": subtitle,
                "text": texts[status],
                "projects": [p for p in projects if p.status == status],
            }
        )
    context = {
        "inner": page,
        "collections": collections,
        "total": len(projects),
        "residential_count": sum(p.is_residential for p in projects),
        "commercial_count": sum(p.is_commercial for p in projects),
        "locations": sorted({p.location for p in projects}),
    }
    return render(request, "projects/list.html", context)


def _published_project(request, slug):
    return get_object_or_404(
        Project.objects.for_builder(request.builder).published().prefetch_related("highlights", "configurations", "gallery"),
        slug=slug,
    )


def _render_project(request, project, page):
    """The project's page: its landing page design when it has one, else the standard project page."""
    related = Project.objects.for_builder(request.builder).published().filter(status=project.status).exclude(pk=project.pk)[:3]
    context = {"project": project, "related": related}
    templates = ["projects/detail.html"]
    if page is not None and page.template in landing.PROJECT_TEMPLATES:
        context.update(landing.context(page, rera=project.rera))
        context["site"] = landing.with_page_contact(SiteSettings.load(request.builder), context["t"])
        templates.insert(0, f"projects/landing/{page.template}.html")
    return render(request, templates, context)


@require_GET
def project_detail(request, slug):
    project = _published_project(request, slug)
    page = project.landing_pages.filter(is_default=True, is_published=True).first()
    return _render_project(request, project, page)


@require_GET
def project_landing(request, slug, page_slug):
    """One of a project's further landing pages (e.g. one per ad campaign), at /projects/<project>/<page>."""
    project = _published_project(request, slug)
    page = get_object_or_404(LandingPage, project=project, slug=page_slug, is_published=True, is_default=False)
    return _render_project(request, project, page)


@require_GET
def billionaire_block(request):
    # Hero media, form and footer texts are on “Billionaire Block page”; everything else is the
    # “Billionaire Block” landing page (projects/landing_pages/billionaire.py). Only builders with that page have it.
    page = BillionaireBlockPage.objects.for_builder(request.builder).first()
    if page is None:
        raise Http404
    context = {
        **(landing.context(landing.builder_page(request.builder, landing.BILLIONAIRE), rera=page.rera_number) or {}),
        "page": page,
        "site": SiteSettings.load(request.builder),
        "residences": page.residences.filter(is_published=True),
        "home_url": reverse("core:home"),
    }
    return render(request, "projects/billionaire_block.html", context)
