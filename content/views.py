from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from content.models import Insight
from core.models import InnerPage
from core.views import inner_page


@require_GET
def insight_list(request):
    insights = list(Insight.objects.for_builder(request.builder).filter(is_published=True))
    featured = next((i for i in insights if i.is_featured), insights[0] if insights else None)
    context = {
        "inner": inner_page(request.builder, InnerPage.Key.INSIGHTS),
        "featured": featured,
        "insights": [i for i in insights if i != featured],
        "categories": sorted({i.category for i in insights}),
    }
    return render(request, "insights/list.html", context)


@require_GET
def insight_detail(request, slug):
    published = Insight.objects.for_builder(request.builder).filter(is_published=True)
    insight = get_object_or_404(published, slug=slug)
    others = published.exclude(pk=insight.pk)
    related = list(others.filter(category=insight.category)[:3])
    if len(related) < 3:
        related += list(others.exclude(pk__in=[i.pk for i in related])[: 3 - len(related)])
    return render(request, "insights/detail.html", {"insight": insight, "related": related})
