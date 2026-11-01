from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from tenants.admin_scoping import TenantScopedAdmin

from content.models import Insight, JourneyPrinciple, JourneyStat, MediaImage, Milestone, PressItem, Publication, Video


def image_preview(obj):
    if not obj.image:
        return ""
    return format_html('<img src="{}" style="width:72px;height:48px;object-fit:cover;border-radius:4px">', obj.image.url)


image_preview.short_description = ""


class OrderedAdmin(TenantScopedAdmin, ModelAdmin):
    list_editable = ["order", "is_published"]


@admin.register(JourneyPrinciple)
class JourneyPrincipleAdmin(OrderedAdmin):
    list_display = ["title", "order", "is_published"]


@admin.register(JourneyStat)
class JourneyStatAdmin(OrderedAdmin):
    list_display = ["value", "label", "order", "is_published"]


@admin.register(Milestone)
class MilestoneAdmin(OrderedAdmin):
    list_display = ["marker", "title", "order", "is_published"]
    list_display_links = ["marker", "title"]


@admin.register(Publication)
class PublicationAdmin(TenantScopedAdmin, ModelAdmin):
    list_display = ["logo_preview", "name", "website", "item_count"]
    list_display_links = ["logo_preview", "name"]
    search_fields = ["name"]

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        if not obj.logo:
            return "—"
        return format_html('<img src="{}" style="height:28px;max-width:140px;object-fit:contain">', obj.logo.url)

    @admin.display(description="News items")
    def item_count(self, obj):
        return obj.items.count()


@admin.register(PressItem)
class PressItemAdmin(OrderedAdmin):
    list_display = ["logo", "title", "published_on", "order", "is_published"]
    list_display_links = ["title"]
    list_filter = ["publication", "is_published"]
    list_select_related = ["publication"]
    search_fields = ["title", "publication__name"]
    date_hierarchy = "published_on"
    fields = ["publication", "title", "published_on", "summary", "article_url", "image", "order", "is_published"]

    @admin.display(description="Publication")
    def logo(self, obj):
        if obj.publication.logo:
            return format_html(
                '<img src="{}" alt="{}" style="height:22px;max-width:120px;object-fit:contain">',
                obj.publication.logo.url,
                obj.publication.name,
            )
        return obj.publication.name


@admin.register(MediaImage)
class MediaImageAdmin(OrderedAdmin):
    list_display = [image_preview, "caption", "category", "order", "is_published"]
    list_display_links = ["caption"]
    list_editable = ["category", "order", "is_published"]
    list_filter = ["category", "is_published"]


@admin.register(Video)
class VideoAdmin(OrderedAdmin):
    list_display = ["title", "youtube_url", "order", "is_published"]


@admin.register(Insight)
class InsightAdmin(OrderedAdmin):
    list_display = [image_preview, "title", "category", "published_on", "is_featured", "order", "is_published"]
    list_display_links = ["title"]
    list_editable = ["is_featured", "order", "is_published"]
    list_filter = ["category", "is_published"]
    search_fields = ["title", "description", "body"]
    prepopulated_fields = {"slug": ["title"]}
    fieldsets = [
        (None, {"fields": ["title", "slug", "category", "image", "description"]}),
        ("Article", {"fields": ["body", "author", "published_on"]}),
        ("Display", {"fields": ["is_featured", "order", "is_published"]}),
    ]
