from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from content.models import Insight, JourneyPrinciple, JourneyStat, MediaImage, Milestone, PressItem, Publication, Video
from core.models import FAQ, HeroBanner, HomePage, InnerPage, Page
from projects.models import BillionaireBlockPage, Project

HOME_MEDIA_COUNT = 8  # Fills the homepage gallery grid exactly (3 rows).
HOME_LIST_COUNT = 3


def inner_page(builder, key):
    page = InnerPage.for_key(builder, key)
    if page is None:
        raise Http404("This menu page has not been set up for this builder yet.")
    return page


def featured_publications(builder):
    """Publications with at least one visible news item, for the "As featured in" strip."""
    return Publication.objects.for_builder(builder).filter(items__is_published=True).distinct()


@require_GET
def home(request):
    builder = request.builder
    projects = Project.objects.for_builder(builder).published()
    press = PressItem.objects.for_builder(builder).filter(is_published=True).select_related("publication")
    publications = featured_publications(builder)
    images = MediaImage.objects.for_builder(builder).filter(is_published=True)
    insights = Insight.objects.for_builder(builder).filter(is_published=True)
    page = HomePage.load(builder)
    context = {
        "page": page,
        "billionaire": BillionaireBlockPage.objects.for_builder(builder).first(),
        "banners": HeroBanner.objects.for_builder(builder).filter(is_active=True),
        "projects": projects.for_homepage(HOME_LIST_COUNT),
        "project_total": projects.count(),
        "guided_projects": projects,
        "principles": JourneyPrinciple.objects.for_builder(builder).filter(is_published=True),
        "stats": JourneyStat.objects.for_builder(builder).filter(is_published=True),
        "press_items": press[:HOME_LIST_COUNT],
        "press_publications": publications,
        "media_images": images[:HOME_MEDIA_COUNT],
        "insights": insights[:HOME_LIST_COUNT],
        # Figures shown beside each section heading, counted from the live content.
        # Company-wide figures from the admin; otherwise counted from the projects on this site.
        "projects_facts": page.projects_fact_list
        or [
            (projects.count(), "Addresses"),
            (projects.filter(is_residential=True).count(), "Residential"),
            (projects.filter(is_commercial=True).count(), "Commercial"),
        ],
        "news_facts": [
            (press.count(), "Stories"),
            (publications.count(), "Publications"),
        ],
        "media_facts": [
            (images.count(), "Images"),
            (images.order_by().values("category").distinct().count(), "Collections"),
        ],
    }
    latest = press.order_by("-published_on").first()
    if latest:
        context["news_facts"].append((latest.published_on.strftime("%b %Y"), "Latest story"))
    videos = Video.objects.for_builder(builder).filter(is_published=True).count()
    if videos:
        context["media_facts"].append((videos, "Films"))
    return render(request, "home/home.html", context)


@require_GET
def journey(request):
    builder = request.builder
    architecture = MediaImage.objects.for_builder(builder).filter(
        is_published=True, category=MediaImage.Category.ARCHITECTURE
    )
    context = {
        "inner": inner_page(builder, InnerPage.Key.JOURNEY),
        "home": HomePage.load(builder),
        "principles": JourneyPrinciple.objects.for_builder(builder).filter(is_published=True),
        "stats": JourneyStat.objects.for_builder(builder).filter(is_published=True),
        "milestones": Milestone.objects.for_builder(builder).filter(is_published=True),
        "story_images": list(architecture[:2]),
        "featured_projects": Project.objects.for_builder(builder).for_homepage(HOME_LIST_COUNT),
    }
    return render(request, "pages/journey.html", context)


@require_GET
def media(request):
    builder = request.builder
    images = list(MediaImage.objects.for_builder(builder).filter(is_published=True))
    used = {image.category for image in images}
    context = {
        "inner": inner_page(builder, InnerPage.Key.MEDIA),
        "images": images,
        "categories": [(value, label) for value, label in MediaImage.Category.choices if value in used],
        "videos": [video for video in Video.objects.for_builder(builder).filter(is_published=True) if video.youtube_id],
        "press_items": PressItem.objects.for_builder(builder).filter(is_published=True).select_related("publication"),
        "press_publications": featured_publications(builder),
    }
    return render(request, "pages/media.html", context)


@require_GET
def contact(request):
    builder = request.builder
    context = {
        "inner": inner_page(builder, InnerPage.Key.CONTACT),
        "faqs": FAQ.objects.for_builder(builder).filter(is_published=True),
        "projects": Project.objects.for_builder(builder).published(),
    }
    return render(request, "pages/contact.html", context)


@require_GET
def page(request, slug):
    page = get_object_or_404(Page.objects.for_builder(request.builder), slug=slug, is_published=True)
    return render(request, "pages/page.html", {"page": page})


@require_GET
def styleguide(request):
    colors = [
        {"name": "Ink", "value": "#0E0E0E", "class_name": "swatch--ink"},
        {"name": "Ivory", "value": "#F5F1EA", "class_name": "swatch--ivory"},
        {"name": "Stone", "value": "#D9D2C5", "class_name": "swatch--stone"},
        {"name": "Champagne", "value": "#B89B6A", "class_name": "swatch--champagne"},
        {"name": "Warm grey", "value": "#6E6A64", "class_name": "swatch--warm-grey"},
    ]
    return render(request, "pages/styleguide.html", {"colors": colors})


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /styleguide",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def healthz(request):
    """For the load balancer / uptime monitor: the app is up and the database answers. No builder needed."""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return HttpResponse("database unavailable\n", status=503, content_type="text/plain")
    return HttpResponse("ok\n", content_type="text/plain")
