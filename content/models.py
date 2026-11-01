import math
import re

from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.images import ResizingImageField
from tenants.query import BuilderUploadTo, TenantQuerySet


class OrderedModel(models.Model):
    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    is_published = models.BooleanField("Show on site", default=True)

    class Meta:
        abstract = True
        ordering = ["order", "id"]


class JourneyPrinciple(OrderedModel):
    title = models.CharField(max_length=120)
    description = models.TextField()

    class Meta(OrderedModel.Meta):
        verbose_name = "Journey value"

    def __str__(self):
        return self.title


class JourneyStat(OrderedModel):
    value = models.CharField(max_length=20, help_text="e.g. “2010” or “66”.")
    label = models.CharField(max_length=80)

    class Meta(OrderedModel.Meta):
        verbose_name = "Journey statistic"

    def __str__(self):
        return f"{self.value} {self.label}"


class Milestone(OrderedModel):
    """A step on the Our Journey timeline."""

    marker = models.CharField(max_length=30, help_text="Short label on the timeline, e.g. “2010” or “Today”.")
    title = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    image = ResizingImageField(upload_to=BuilderUploadTo("milestones"), blank=True)

    class Meta(OrderedModel.Meta):
        verbose_name = "Journey milestone"

    def __str__(self):
        return f"{self.marker} · {self.title}"


class Publication(models.Model):
    """A newspaper or website that covered the builder; its logo is shown on news cards."""

    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    name = models.CharField(max_length=80)
    logo = ResizingImageField(
        upload_to=BuilderUploadTo("press/logos"),
        help_text="Official logo, ideally a wide PNG with a transparent or white background.",
    )
    website = models.URLField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["builder", "name"], name="content_publication_unique_name_per_builder")
        ]

    def __str__(self):
        return self.name


class PressItem(OrderedModel):
    title = models.CharField(max_length=255, help_text="The headline exactly as the publication printed it.")
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT, related_name="items")
    published_on = models.DateField()
    summary = models.TextField(help_text="One or two sentences on what the article reports.")
    image = ResizingImageField(
        upload_to=BuilderUploadTo("press"), blank=True, help_text="Optional. Shown only if the publication has no logo."
    )
    article_url = models.URLField(max_length=2000, help_text="Link to the article on the publication's website.")

    @property
    def source(self):
        return self.publication.name

    class Meta:
        ordering = ["order", "-published_on", "id"]
        verbose_name = "Press / news item"
        verbose_name_plural = "Press / news"

    def __str__(self):
        return self.title


class MediaImage(OrderedModel):
    class Category(models.TextChoices):
        ARCHITECTURE = "architecture", "Architecture"
        INTERIORS = "interiors", "Interiors"
        AMENITIES = "amenities", "Amenities"
        OUTDOORS = "outdoors", "Outdoors & leisure"

    image = ResizingImageField(upload_to=BuilderUploadTo("media-gallery"))
    caption = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.ARCHITECTURE)

    class Meta(OrderedModel.Meta):
        verbose_name = "Media gallery image"

    def __str__(self):
        return self.caption


class Video(OrderedModel):
    title = models.CharField(max_length=160)
    youtube_url = models.URLField(help_text="Paste the YouTube link, e.g. https://www.youtube.com/watch?v=…")
    description = models.CharField(max_length=255, blank=True)

    class Meta(OrderedModel.Meta):
        pass

    def __str__(self):
        return self.title

    @property
    def youtube_id(self):
        match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([\w-]{11})", self.youtube_url)
        return match.group(1) if match else ""


class Insight(OrderedModel):
    image = ResizingImageField(upload_to=BuilderUploadTo("insights"))
    category = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, help_text="Page address: /insights/<slug>")
    description = models.TextField(help_text="Short summary shown on cards and in Google.")
    body = models.TextField(
        help_text=(
            "The article. Leave a blank line between paragraphs. "
            "Start a line with ## to make it a sub-heading."
        )
    )
    author = models.CharField(max_length=80, default="M3M India Editorial")
    published_on = models.DateField(default=timezone.localdate)
    is_featured = models.BooleanField(
        "Feature at top of Insights page", default=False
    )

    class Meta:
        ordering = ["order", "-published_on", "id"]
        constraints = [models.UniqueConstraint(fields=["builder", "slug"], name="content_insight_unique_slug_per_builder")]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("insight_detail", args=[self.slug])

    @property
    def reading_minutes(self):
        return max(1, math.ceil(len(self.body.split()) / 220))

    @property
    def blocks(self):
        """Body split into ("h", text) sub-headings and ("p", text) paragraphs."""
        result = []
        for chunk in re.split(r"\n\s*\n", self.body.strip()):
            chunk = chunk.strip()
            if chunk.startswith("## "):
                result.append(("h", chunk[3:].strip()))
            elif chunk:
                result.append(("p", " ".join(chunk.split())))
        return result
