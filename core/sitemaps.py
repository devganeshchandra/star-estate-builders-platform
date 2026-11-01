from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from django.urls import reverse

from content.models import Insight
from core.models import InnerPage, Page
from projects.models import BillionaireBlockPage, LandingPage, Project


class BuilderSitemap(Sitemap):
    """A sitemap section listing one builder's pages. Addresses use the host the sitemap was requested on."""

    def __init__(self, builder):
        self.builder = builder


class HomeSitemap(BuilderSitemap):
    priority = 1.0
    changefreq = "weekly"

    def items(self):
        return ["core:home"]

    def location(self, item):
        return reverse(item)


class BillionaireBlockSitemap(BuilderSitemap):
    priority = 0.9
    changefreq = "weekly"

    def items(self):
        has_page = BillionaireBlockPage.objects.for_builder(self.builder).exists()
        return ["projects:billionaire_block"] if has_page else []

    def location(self, item):
        return reverse(item)


class MenuPageSitemap(BuilderSitemap):
    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return InnerPage.objects.for_builder(self.builder)

    def lastmod(self, obj):
        return obj.updated_at


class InsightSitemap(BuilderSitemap):
    priority = 0.6
    changefreq = "monthly"

    def items(self):
        return Insight.objects.for_builder(self.builder).filter(is_published=True)

    def lastmod(self, obj):
        return obj.published_on


class ProjectSitemap(BuilderSitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return Project.objects.for_builder(self.builder).published()

    def lastmod(self, obj):
        return obj.updated_at


class LandingPageSitemap(BuilderSitemap):
    """A project's further landing pages (its main page is listed with the project)."""

    priority = 0.7
    changefreq = "weekly"

    def items(self):
        return (
            LandingPage.objects.for_builder(self.builder)
            .filter(is_published=True, is_default=False, project__is_published=True)
            .select_related("project")
        )

    def lastmod(self, obj):
        return obj.updated_at


class PageSitemap(BuilderSitemap):
    priority = 0.3

    def items(self):
        return Page.objects.for_builder(self.builder).filter(is_published=True)

    def lastmod(self, obj):
        return obj.updated_at


SECTIONS = {
    "home": HomeSitemap,
    "billionaire-block": BillionaireBlockSitemap,
    "menu": MenuPageSitemap,
    "projects": ProjectSitemap,
    "landing-pages": LandingPageSitemap,
    "insights": InsightSitemap,
    "pages": PageSitemap,
}


def builder_sitemap(request):
    sitemaps = {name: section(request.builder) for name, section in SECTIONS.items()}
    return sitemap(request, sitemaps)
