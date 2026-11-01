from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.images import ResizingImageField
from core.models import SingletonModel
from tenants.query import BuilderUploadTo, TenantQuerySet


class ProjectQuerySet(TenantQuerySet):
    def published(self):
        return self.filter(is_published=True)

    def for_homepage(self, limit=3):
        """Featured projects first; topped up from the rest when fewer are featured."""
        projects = list(self.published().filter(is_featured=True)[:limit])
        if len(projects) < limit:
            exclude = [p.pk for p in projects]
            projects += list(self.published().exclude(pk__in=exclude)[: limit - len(projects)])
        return projects


class Project(models.Model):
    """A project and its landing page at /projects/<slug>."""

    class Status(models.TextChoices):
        DELIVERED = "delivered", "Delivered Landmarks (completed & handed over)"
        CURRENT = "current", "Now Presenting (available now)"
        UPCOMING = "upcoming", "On the Horizon (upcoming)"

    # Public names and descriptions of each collection on the Projects page.
    COLLECTIONS = {
        Status.DELIVERED: ("Delivered Landmarks", "Completed & handed over"),
        Status.CURRENT: ("Now Presenting", "Available to own today"),
        Status.UPCOMING: ("On the Horizon", "Upcoming launches"),
    }

    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="projects")
    tenant_path = "builder"

    name = models.CharField(max_length=120)
    slug = models.SlugField(
        max_length=120,
        help_text="Used in the page address: /projects/your-project-name. Changing it breaks old links.",
    )
    category = models.CharField(
        max_length=80, help_text="Brand / collection shown above the name, e.g. “M3M The Line”."
    )
    is_residential = models.BooleanField("Residential", default=False)
    is_commercial = models.BooleanField("Commercial", default=False)
    offering = models.CharField(max_length=160, help_text="e.g. “3, 4 & 5 BHK Apartments”.")
    location = models.CharField(max_length=120, help_text="e.g. “Sector 97, Noida Expressway”.")
    city = models.CharField(max_length=60, default="Noida")
    rera = models.CharField("RERA number", max_length=80)
    image = ResizingImageField(upload_to=BuilderUploadTo("projects"), help_text="Main project image (landscape).")
    summary = models.TextField(help_text="Short description used on the card, page and in Google.")
    status = models.CharField(
        "Collection",
        max_length=20,
        choices=Status.choices,
        default=Status.CURRENT,
        help_text="Which collection the project appears in on the Projects page.",
    )
    timeline_note = models.CharField(
        max_length=80,
        blank=True,
        help_text="Optional short note on the card, e.g. “Possession from 2029” or “Handed over 2024”.",
    )
    is_featured = models.BooleanField(
        "Show on homepage",
        default=False,
        help_text="The homepage shows up to 3 featured projects (in order).",
    )

    # Landing page
    headline = models.CharField(
        max_length=120, default="A place to make your own.", help_text="Big heading in the overview."
    )
    overview_label = models.CharField(max_length=60, default="The address")
    description = models.TextField(
        blank=True, help_text="Optional longer description. Leave a blank line between paragraphs."
    )
    brochure = models.FileField(upload_to=BuilderUploadTo("brochures"), blank=True, help_text="Optional PDF brochure.")
    map_embed_url = models.URLField(
        blank=True,
        max_length=1000,
        help_text="Optional Google Maps “Embed a map” link (the src=… URL only).",
    )

    # SEO
    seo_title = models.CharField(max_length=120, blank=True, help_text="Defaults to the project name.")
    seo_description = models.CharField(max_length=300, blank=True, help_text="Defaults to the summary.")

    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    is_published = models.BooleanField("Show on site", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["order", "id"]
        # The same project name and address may exist for several builders (e.g. m3m + jacob, ace + jacob).
        constraints = [models.UniqueConstraint(fields=["builder", "slug"], name="projects_project_unique_slug_per_builder")]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("projects:detail", args=[self.slug])

    @property
    def collection_name(self):
        return self.COLLECTIONS[self.status][0]

    @property
    def interests(self):
        return [
            interest
            for interest, enabled in (("residential", self.is_residential), ("commercial", self.is_commercial))
            if enabled
        ]


class ProjectHighlight(models.Model):
    tenant_path = "project__builder"

    objects = TenantQuerySet.as_manager()

    project = models.ForeignKey(Project, related_name="highlights", on_delete=models.CASCADE)
    title = models.CharField(max_length=120)
    text = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class ProjectConfiguration(models.Model):
    """A unit type / floor plan row, e.g. “3 BHK · 2,450 sq. ft.”."""

    tenant_path = "project__builder"

    objects = TenantQuerySet.as_manager()

    project = models.ForeignKey(Project, related_name="configurations", on_delete=models.CASCADE)
    unit_type = models.CharField(max_length=80)
    size = models.CharField(max_length=80, blank=True)
    price = models.CharField(max_length=80, blank=True, help_text="e.g. “Price on request”.")
    floor_plan = ResizingImageField(upload_to=BuilderUploadTo("floor-plans"), blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Configuration / floor plan"
        verbose_name_plural = "Configurations / floor plans"

    def __str__(self):
        return self.unit_type


class ProjectImage(models.Model):
    tenant_path = "project__builder"

    objects = TenantQuerySet.as_manager()

    project = models.ForeignKey(Project, related_name="gallery", on_delete=models.CASCADE)
    image = ResizingImageField(upload_to=BuilderUploadTo("projects/gallery"))
    caption = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Gallery image"

    def __str__(self):
        return self.caption or f"Image {self.pk}"


class BillionaireBlockPage(SingletonModel):
    """Headings, texts and media of the Billionaire Block page at /billionaire-block.

    Lists (figures, features, club, services, security, distances, gallery, specifications) are
    “Billionaire Block content items”; residence types are edited in the tab above.
    """

    # Hero
    hero_video = models.FileField(
        upload_to=BuilderUploadTo("billionaire-block"), blank=True, help_text="Silent MP4 loop, 10–20 seconds. Leave empty to show the image."
    )
    hero_image = ResizingImageField(
        upload_to=BuilderUploadTo("billionaire-block"), blank=True, help_text="Shown while the video loads, and on its own without a video."
    )
    hero_image_alt = models.CharField(max_length=160, default="Billionaire Block towers above the clouds, artistic impression")
    eyebrow = models.CharField(max_length=80, default="Sector 111 · Dwarka Expressway · Gurugram")
    title = models.CharField(max_length=60, default="Billionaire Block")
    tagline = models.CharField(max_length=160, default="A 170-acre enclave of global branded residences.")

    # Teaser shown on the homepage, linking to this page
    teaser_label = models.CharField(max_length=80, default="The future of M3M")
    teaser_heading = models.CharField(max_length=160, default="Something extraordinary is rising.")
    teaser_text = models.TextField(
        default=(
            "A 170-acre enclave of globally branded residences in Sector 111, Gurugram, beginning with Signature "
            "Residences by ELIE SAAB."
        )
    )
    teaser_button = models.CharField(max_length=60, default="Explore Billionaire Block")

    # About the project and what is being built (just below the hero)
    about_label = models.CharField(max_length=80, default="About the project")
    about_heading = models.CharField(max_length=160, default="A 170-acre address for the world’s finest names.")
    about_text = models.TextField(
        default=(
            "A 170-acre enclave for global branded residences, within M3M’s Smart City Delhi Airport township "
            "in Sector 111, on Gurugram’s Dwarka Expressway."
        ),
        help_text="Leave a blank line between paragraphs.",
    )
    about_image = ResizingImageField(upload_to=BuilderUploadTo("billionaire-block"), blank=True)
    about_image_2 = ResizingImageField(
        upload_to=BuilderUploadTo("billionaire-block"), blank=True, help_text="Optional. Stacked under the first image."
    )
    about_facts = models.TextField(
        blank=True,
        default=(
            "170 acres | The Billionaire’s Block enclave\n"
            "SCDA | Smart City Delhi Airport, M3M’s mixed-use township\n"
            "Sector 111 | Dwarka Expressway, Gurugram"
        ),
        help_text="One per line, as “figure | label”.",
    )
    building_label = models.CharField(max_length=80, default="What we are building")
    building_heading = models.CharField(max_length=160, default="Branded residences, couture-coded.")
    building_text = models.TextField(
        default=(
            "First in the enclave: Signature Residences by ELIE SAAB. Four-bedroom homes with waterfront views, "
            "wrap-around decks and private jacuzzis."
        ),
        help_text="Leave a blank line between paragraphs.",
    )
    building_image = ResizingImageField(upload_to=BuilderUploadTo("billionaire-block"), blank=True)
    building_image_2 = ResizingImageField(
        upload_to=BuilderUploadTo("billionaire-block"), blank=True, help_text="Optional. Stacked under the first image."
    )
    building_points = models.TextField(
        blank=True,
        default=(
            "300 four-bedroom residences\n"
            "4,200 to 4,650 sq ft each\n"
            "Interiors with Carlo Colombo\n"
            "Completion scheduled for 2030"
        ),
        help_text="One point per line.",
    )
    building_note = models.CharField(
        max_length=200, blank=True, default="Figures as reported by Business Today and Outlook Luxe, January 2026."
    )

    # News (the stories themselves are in the “News” tab)
    news_label = models.CharField(max_length=80, default="In the news")
    news_heading = models.CharField(max_length=160, default="The plan, as reported.")
    news_intro = models.TextField(
        default="What leading publications have reported about the Billionaire’s Block and its first branded residences."
    )

    # Manifesto
    manifesto_heading = models.CharField(max_length=160, default="Some addresses are bought. This one is earned.")
    manifesto_text = models.TextField(
        default=(
            "Couture design, Italian craft and a 170-acre setting, brought together at one address."
        )
    )

    # Architecture
    architecture_label = models.CharField(max_length=80, default="Architecture & design")
    architecture_heading = models.CharField(max_length=160, default="ELIE SAAB. Inside and out.")
    architecture_text = models.TextField(
        default=(
            "Interiors created with designer Carlo Colombo and furnished from the ELIE SAAB Maison collection, "
            "crafted in Italy. Common areas are fully furnished by ELIE SAAB."
        ),
        help_text="Leave a blank line between paragraphs.",
    )
    architecture_image = ResizingImageField(upload_to=BuilderUploadTo("billionaire-block"), blank=True)
    credit_1_label = models.CharField(max_length=40, blank=True, default="Design house")
    credit_1_value = models.CharField(max_length=120, blank=True, default="ELIE SAAB")
    credit_2_label = models.CharField(max_length=40, blank=True, default="Interiors")
    credit_2_value = models.CharField(max_length=120, blank=True, default="Carlo Colombo")
    credit_3_label = models.CharField(max_length=40, blank=True, default="Furniture")
    credit_3_value = models.CharField(max_length=120, blank=True, default="ELIE SAAB Maison, crafted in Italy")

    # Section headings
    residences_label = models.CharField(max_length=80, default="The residences")
    residences_heading = models.CharField(max_length=160, default="Four bedrooms. Three hundred homes.")
    features_label = models.CharField(max_length=80, default="Amenities")
    features_heading = models.CharField(max_length=160, default="As announced for residents.")
    features_intro = models.TextField(
        default="Announced at launch. Full details will follow in the official project documents."
    )
    club_label = models.CharField(max_length=80, default="Amenities")
    club_heading = models.CharField(max_length=160, default="Announced for residents.")
    club_intro = models.TextField(
        default="Seven amenities named at launch. Images are representative."
    )
    amenities_label = models.CharField(max_length=80, default="Lifestyle")
    amenities_heading = models.CharField(max_length=160, default="Live well, indoors and out.")
    amenities_intro = models.TextField(
        default="Representative imagery. The final amenity list will follow the official project documents."
    )
    amenities_indoor_heading = models.CharField(max_length=120, default="World-class indoor amenities")
    amenities_wellness_heading = models.CharField(max_length=120, default="Amenities curated for wellness")
    amenities_leisure_heading = models.CharField(max_length=120, default="Leisure spaces for all generations")
    services_label = models.CharField(max_length=80, default="The vision")
    services_heading = models.CharField(max_length=160, default="Built on four ideas.")
    services_intro = models.TextField(
        default="The thinking behind the Billionaire’s Block."
    )
    security_label = models.CharField(max_length=80, default="The township")
    security_heading = models.CharField(max_length=160, default="A city around the enclave.")
    security_text = models.TextField(
        default="Smart City Delhi Airport: M3M’s mixed-use township around the enclave.",
    )
    security_image = ResizingImageField(upload_to=BuilderUploadTo("billionaire-block"), blank=True)
    location_label = models.CharField(max_length=80, default="Location")
    location_heading = models.CharField(max_length=160, default="Sector 111, Dwarka Expressway.")
    location_text = models.TextField(
        default="Planned around easy access to the airport, Delhi and Gurugram’s business districts."
    )
    location_note = models.CharField(max_length=160, default="Travel times depend on the route and traffic, so none are quoted here.")
    map_embed_url = models.URLField(
        max_length=1000,
        default="https://www.google.com/maps?q=Sector+111,+Dwarka+Expressway,+Gurugram&output=embed",
        help_text="Google Maps → Share → Embed a map → copy the src=… link.",
    )
    gallery_label = models.CharField(max_length=80, default="Gallery · Artistic impressions")
    gallery_heading = models.CharField(max_length=160, default="A closer look.")
    specs_label = models.CharField(max_length=80, default="Before you buy")
    specs_heading = models.CharField(max_length=160, default="Questions worth asking.")
    specs_intro = models.TextField(
        default="Check each against the project’s RERA disclosures and your agreement. Not legal advice."
    )
    specs_image = ResizingImageField(upload_to=BuilderUploadTo("billionaire-block"), blank=True)

    # Developer legacy (figures come from “Journey statistics”, projects from “Delivered Landmarks”)
    legacy_label = models.CharField(max_length=80, default="The developer")
    legacy_heading = models.CharField(max_length=160, default="A legacy written in landmarks.")
    legacy_text = models.TextField(
        default=(
            "Since 2010, M3M India has built a reputation on addresses that change how a city sees itself."
        )
    )

    # Private viewing form
    form_label = models.CharField(max_length=80, default="Private viewing")
    form_heading = models.CharField(max_length=120, default="Request a Private Viewing")
    form_intro = models.TextField(
        default="Our team will share the project details and arrange a presentation at your convenience."
    )
    form_success_title = models.CharField(max_length=120, default="Your request is received.")
    form_success_text = models.TextField(
        default="Our team will call you to arrange your presentation."
    )
    form_note = models.CharField(max_length=160, default="Your details are held in strict confidence.")
    viewing_steps = models.TextField(
        blank=True,
        default=(
            "A call from our team\n"
            "A presentation of the residences\n"
            "A site visit, if you wish"
        ),
        help_text="“What happens next”, one step per line.",
    )

    # Brochure
    brochure = models.FileField(upload_to=BuilderUploadTo("billionaire-block"), blank=True, help_text="PDF. Visitors share their name and phone first.")
    brochure_heading = models.CharField(max_length=120, default="The private brochure")
    brochure_text = models.CharField(
        max_length=200, default="Share your name and number and the brochure is yours."
    )

    # Footer
    rera_number = models.CharField(
        max_length=80, blank=True, help_text="Project RERA registration number. Shown in the footer once filled in."
    )
    footer_disclaimer = models.TextField(
        default=(
            "All images are artistic impressions. Figures, specifications, amenities and services are indicative and "
            "subject to approvals and the final project documents. This page is not an offer or an invitation to buy."
        )
    )

    seo_title = models.CharField(max_length=120, default="M3M Billionaire Block, Sector 111 Gurugram | ELIE SAAB Residences")
    seo_description = models.CharField(
        max_length=300,
        default=(
            "M3M Billionaire Block: a 170-acre enclave on Dwarka Expressway, Gurugram, beginning with 300 "
            "four-bedroom Signature Residences by ELIE SAAB. Enquire now."
        ),
    )

    class Meta:
        verbose_name = "Billionaire Block page"
        verbose_name_plural = "Billionaire Block page"

    def __str__(self):
        return "Billionaire Block page"

    def get_absolute_url(self):
        return reverse("projects:billionaire_block")

    @staticmethod
    def _lines(text):
        return [line.strip() for line in text.splitlines() if line.strip()]

    @property
    def about_fact_list(self):
        facts = []
        for line in self._lines(self.about_facts):
            value, _, label = line.partition("|")
            facts.append((value.strip(), label.strip()))
        return facts

    @property
    def building_point_list(self):
        return self._lines(self.building_points)

    @property
    def viewing_step_list(self):
        return self._lines(self.viewing_steps)

    @property
    def credits(self):
        pairs = [
            (self.credit_1_label, self.credit_1_value),
            (self.credit_2_label, self.credit_2_value),
            (self.credit_3_label, self.credit_3_value),
        ]
        return [(label, value) for label, value in pairs if label and value]


class BillionaireResidence(models.Model):
    """A residence type, e.g. Sky Villas, with its floor plan."""

    tenant_path = "page__builder"

    objects = TenantQuerySet.as_manager()

    page = models.ForeignKey(BillionaireBlockPage, related_name="residences", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    tagline = models.CharField(max_length=160, blank=True)
    image = ResizingImageField(upload_to=BuilderUploadTo("billionaire-block"))
    image_alt = models.CharField(max_length=160, blank=True)
    size = models.CharField(max_length=80, help_text="e.g. “10,000 – 12,500 sq ft”.")
    configuration = models.CharField(max_length=120, help_text="e.g. “4 & 5 bedrooms with staff quarters”.")
    features = models.TextField(blank=True, help_text="One feature per line.")
    floor_plan = ResizingImageField(
        upload_to=BuilderUploadTo("billionaire-block/floor-plans"), blank=True, help_text="Leave empty to offer the plan on request."
    )
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField("Show on site", default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Residence type"

    def __str__(self):
        return self.name

    @property
    def feature_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]


class BillionaireItem(models.Model):
    """One entry in a list on the Billionaire Block page; `section` decides where it appears."""

    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    class Section(models.TextChoices):
        STAT = "stat", "Key numbers"
        FEATURE = "feature", "Residence features"
        CLUB = "club", "Amenities (with image)"
        SERVICE = "service", "The vision"
        SECURITY = "security", "The township"
        LOCATION = "location", "Location distances"
        GALLERY = "gallery", "Gallery (with image)"
        AMENITY_INDOOR = "amenity_indoor", "Amenities: indoor"
        AMENITY_WELLNESS = "amenity_wellness", "Amenities: wellness"
        AMENITY_LEISURE = "amenity_leisure", "Amenities: leisure"
        SPEC = "spec", "Before you buy"

    section = models.CharField(max_length=20, choices=Section.choices)
    title = models.CharField(max_length=120, help_text="Name, label or caption.")
    value = models.CharField(
        max_length=60, blank=True, help_text="Key numbers: the figure, e.g. “12,000+”. Distances: the time, e.g. “15 min”."
    )
    text = models.TextField(blank=True, help_text="Short description. Key numbers: the unit, e.g. “sq ft”.")
    image = ResizingImageField(upload_to=BuilderUploadTo("billionaire-block"), blank=True)
    image_alt = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField("Show on site", default=True)

    class Meta:
        ordering = ["section", "order", "id"]
        verbose_name = "Billionaire Block content item"

    def __str__(self):
        return f"{self.get_section_display()}: {self.title}"


class BillionaireNews(models.Model):
    """A published story about the project, shown as a card that opens in a popup."""

    tenant_path = "page__builder"

    objects = TenantQuerySet.as_manager()

    page = models.ForeignKey(BillionaireBlockPage, related_name="news", on_delete=models.CASCADE)
    tag = models.CharField(max_length=40, blank=True, help_text="One word, e.g. “Launch” or “Pricing”.")
    title = models.CharField(max_length=160)
    publication = models.CharField(max_length=80, help_text="e.g. “Business Today” or “PTI via The Week”.")
    published_on = models.DateField()
    summary = models.CharField(max_length=240, help_text="Shown on the card.")
    body = models.TextField(help_text="Shown in the popup. Leave a blank line between paragraphs.")
    key_points = models.TextField(blank=True, help_text="Shown in the popup. One point per line.")
    url = models.URLField("Link to the article", max_length=500)
    is_press_release = models.BooleanField(
        "Paid press release", default=False, help_text="Adds a note that the source is a sponsored release."
    )
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField("Show on site", default=True)

    class Meta:
        ordering = ["order", "-published_on", "id"]
        verbose_name = "News story"
        verbose_name_plural = "News"

    def __str__(self):
        return self.title

    @property
    def key_point_list(self):
        return [line.strip() for line in self.key_points.splitlines() if line.strip()]


class LandingPage(models.Model):
    """The editable content of a custom landing page: its texts, single images and lists.

    The page design lives in its template; every word and picture on it is a row here, so the
    content team can change them in the admin. Rows are created by projects/landing.py.
    """

    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="landing_pages")
    project = models.ForeignKey(
        Project,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="landing_pages",
        help_text="The project this page advertises. Empty for builder-wide pages (e.g. the shared website texts).",
    )
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    slug = models.SlugField(
        max_length=120,
        help_text="Page address: /projects/<project>/<this>. For the project's main page, use the project's own slug.",
    )
    name = models.CharField(max_length=120)
    template = models.CharField(
        max_length=80,
        blank=True,
        help_text="The page design. Its texts, pictures and lists are created from the design's starting content.",
    )
    is_default = models.BooleanField(
        "Project's main page",
        default=False,
        help_text="Shown at /projects/<project>. Other landing pages of the project are at /projects/<project>/<page>.",
    )
    is_published = models.BooleanField("Show on site", default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    seo_title = models.CharField("Browser & Google title", max_length=160, blank=True)
    seo_description = models.CharField("Google description", max_length=300, blank=True)
    share_title = models.CharField(max_length=160, blank=True, help_text="Title when the link is shared, e.g. on WhatsApp.")
    share_description = models.CharField(max_length=300, blank=True)
    share_image = ResizingImageField(upload_to=BuilderUploadTo("landing"), blank=True, help_text="Picture when the link is shared.")

    class Meta:
        ordering = ["name"]
        verbose_name = "Landing page"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "slug"],
                condition=models.Q(project__isnull=False),
                name="projects_landingpage_unique_slug_per_project",
            ),
            models.UniqueConstraint(
                fields=["builder", "slug"],
                condition=models.Q(project__isnull=True),
                name="projects_landingpage_unique_slug_per_builder",
            ),
            models.UniqueConstraint(
                fields=["project"], condition=models.Q(is_default=True), name="projects_landingpage_one_main_page"
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        from projects import landing

        if self.template == landing.BILLIONAIRE:
            return reverse("projects:billionaire_block")
        if self.project_id is None:  # Shared website texts: shown across the site, starting with the homepage.
            return "/"
        if self.is_default:
            return reverse("projects:detail", args=[self.project.slug])
        return reverse("projects:landing", args=[self.project.slug, self.slug])

    def clean(self):
        from projects import landing

        if self.project_id and not self.builder_id:
            self.builder = self.project.builder
        errors = {}
        if self.project_id and self.project.builder_id != self.builder_id:
            errors["project"] = "Choose a project of the same builder."
        if self.project_id and self.template not in landing.PROJECT_TEMPLATES:
            errors["template"] = "Choose a design for this project page."
        if self.is_default and not self.project_id:
            errors["is_default"] = "Only a page with a project can be the project's main page."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.project_id:
            if not self.builder_id:
                self.builder_id = self.project.builder_id
            elif self.project.builder_id != self.builder_id:
                raise ValueError("A landing page and its project must belong to the same builder.")
        super().save(*args, **kwargs)


class LandingText(models.Model):
    """One heading, paragraph, button label or note on a landing page."""

    tenant_path = "page__builder"

    objects = TenantQuerySet.as_manager()

    page = models.ForeignKey(LandingPage, related_name="texts", on_delete=models.CASCADE)
    section = models.CharField(max_length=80)
    key = models.SlugField(max_length=60)
    label = models.CharField(max_length=160)
    value = models.TextField(
        "Text",
        blank=True,
        help_text="Put *stars* around words to show them in italics. {rera} is replaced by the RERA number.",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["page", "key"], name="unique_landing_text")]
        verbose_name = "Text"

    def __str__(self):
        return f"{self.section}: {self.label}"


class LandingImage(models.Model):
    """One fixed picture on a landing page, e.g. a section background."""

    tenant_path = "page__builder"

    objects = TenantQuerySet.as_manager()

    page = models.ForeignKey(LandingPage, related_name="images", on_delete=models.CASCADE)
    section = models.CharField(max_length=80)
    key = models.SlugField(max_length=60)
    label = models.CharField(max_length=160)
    image = ResizingImageField(upload_to=BuilderUploadTo("landing"), blank=True, help_text="Landscape, at least 1600px wide.")
    alt = models.CharField("Description", max_length=240, blank=True, help_text="For screen readers and Google.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["page", "key"], name="unique_landing_image")]
        verbose_name = "Image"

    def __str__(self):
        return f"{self.section}: {self.label}"


class LandingItem(models.Model):
    """One entry in a list on a landing page (a slide, an amenity, a question…); `list_key` decides which."""

    tenant_path = "page__builder"

    objects = TenantQuerySet.as_manager()

    page = models.ForeignKey(LandingPage, related_name="items", on_delete=models.CASCADE)
    list_key = models.CharField("List", max_length=40)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True)
    value = models.CharField(max_length=120, blank=True)
    group = models.CharField(max_length=80, blank=True)
    text = models.TextField(blank=True)
    link = models.CharField(max_length=500, blank=True)
    image = ResizingImageField(upload_to=BuilderUploadTo("landing"), blank=True)
    image_alt = models.CharField("Image description", max_length=240, blank=True)
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")
    is_published = models.BooleanField("Show on site", default=True)

    class Meta:
        ordering = ["list_key", "order", "id"]
        verbose_name = "List item"

    def __str__(self):
        return self.title

    @property
    def lines(self):
        return [line.strip() for line in self.text.splitlines() if line.strip()]
