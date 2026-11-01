from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse

from core.images import ResizingImageField
from tenants.query import BuilderUploadTo, TenantQuerySet

# The field defaults below were written for the first builder. A new builder's row starts from the same
# defaults with these names replaced by its own (SingletonModel.create_for).
FIRST_BUILDER_NAMES = ("M3M India", "M3M")


def rename_first_builder(text, builder):
    for name in FIRST_BUILDER_NAMES:
        text = text.replace(name, builder.name)
    return text


# Branding values are written into the page's CSS, so only plain values are accepted.
HEX_COLOR = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Enter a colour as # and six hex digits, e.g. #172b46.")
FONT_NAME = RegexValidator(r"^[A-Za-z0-9 ]{2,60}$", "Enter a Google Fonts family name, e.g. Playfair Display.")


class SingletonModel(models.Model):
    """One row per builder (its settings, homepage text…), edited from the admin as a single form."""

    builder = models.OneToOneField("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"
    # Fields a new builder starts with empty instead of the first builder's values (phone numbers, address…).
    blank_for_new_builder = ()

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete(self.get_cache_key(self.builder_id))

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_cache_key(cls, builder_id):
        return f"singleton:{cls._meta.label_lower}:{builder_id}"

    @classmethod
    def load(cls, builder):
        """This builder's row, created with starting values the first time it is needed."""
        key = cls.get_cache_key(builder.pk)
        obj = cache.get(key)
        if obj is None:
            obj = cls.objects.filter(builder=builder).first() or cls.create_for(builder)
            cache.set(key, obj, 300)
        return obj

    @classmethod
    def create_for(cls, builder):
        values = {}
        if builder.name not in FIRST_BUILDER_NAMES:  # The defaults were written for the first builder.
            for field in cls._meta.concrete_fields:
                default = field.get_default() if field.has_default() else None
                if isinstance(default, str):
                    values[field.name] = rename_first_builder(default, builder)
            values.update({name: "" for name in cls.blank_for_new_builder})
        obj, _ = cls.objects.get_or_create(builder=builder, defaults=values)
        return obj


class SiteSettings(SingletonModel):
    site_name = models.CharField(max_length=80, default="M3M India")
    default_title = models.CharField(
        max_length=120,
        default="M3M India | Considered Living",
        help_text="Browser tab title for the homepage.",
    )
    meta_description = models.TextField(
        default="A considered expression of place. Explore residences, destinations and spaces by M3M India.",
        help_text="Shown in Google results and social shares.",
    )
    share_image = ResizingImageField(
        upload_to=BuilderUploadTo("site"),
        blank=True,
        help_text="Default image for WhatsApp / social shares (1200×630 recommended).",
    )

    phone_display = models.CharField(max_length=30, default="1800 123 3333")
    phone_dial = models.CharField(
        max_length=20,
        default="18001233333",
        help_text="Number used for click-to-call, digits only (country code optional).",
    )
    phone_international = models.CharField(
        max_length=25, default="+91-1800-123-3333", help_text="Used in search-engine data."
    )
    whatsapp_number = models.CharField(
        max_length=20,
        default="919311995812",
        help_text="WhatsApp number with country code, digits only.",
    )

    address_line_1 = models.CharField(
        max_length=200, default="41st Floor, Tower-1, M3M International Financial Center,"
    )
    address_line_2 = models.CharField(
        max_length=200, default="Sector-66, Golf Course Road (Extn.), Gurugram-122101"
    )
    street_address = models.CharField(
        max_length=255,
        default="41st Floor, Tower-1, M3M International Financial Center, Sector-66, Golf Course Road (Extn.)",
        help_text="Used in search-engine data.",
    )
    city = models.CharField(max_length=80, default="Gurugram")
    postal_code = models.CharField(max_length=12, default="122101")
    email = models.EmailField(blank=True, help_text="Public contact email. Leave empty to hide it.")
    office_hours = models.CharField(
        max_length=120, blank=True, help_text="e.g. “Monday to Saturday, 10 AM – 7 PM”. Leave empty to hide."
    )
    map_embed_url = models.URLField(
        max_length=1000,
        blank=True,
        default=(
            "https://www.google.com/maps?q=M3M+International+Financial+Center,+Sector+66,"
            "+Golf+Course+Road+Extension,+Gurugram&output=embed"
        ),
        help_text="Map on the Contact page. Google Maps → Share → Embed a map → copy the src=… link.",
    )

    footer_disclaimer = models.TextField(
        default=(
            "Images and visuals are artistic impressions and are indicative only. Project plans, "
            "specifications, amenities, areas and other particulars may change, subject to applicable "
            "approvals and the relevant project documents. Prospective buyers should review the "
            "applicable RERA registration and project disclosures before making a decision. Nothing on "
            "this website is an offer, invitation or legal or financial advice. Project-specific "
            "information will be provided with the relevant project materials."
        )
    )
    footer_note = models.CharField(max_length=120, default="", blank=True)

    enquiry_success_message = models.TextField(
        default="Thank you. Your details have been received and our team will be in touch shortly.",
        help_text="Shown to visitors after they submit any enquiry form.",
    )
    lead_notification_emails = models.TextField(
        blank=True,
        help_text="Addresses that get an email for every new lead on this builder's websites, separated by commas.",
    )

    # Branding. Empty values leave the design exactly as its stylesheet defines it.
    logo = ResizingImageField(upload_to=BuilderUploadTo("branding"), blank=True, help_text="Main logo (PNG or WebP).")
    logo_light = ResizingImageField(
        upload_to=BuilderUploadTo("branding"),
        blank=True,
        help_text="Light version for the transparent header over banner pictures. Defaults to the main logo.",
    )
    favicon = models.ImageField(
        upload_to=BuilderUploadTo("branding"), blank=True, help_text="Square PNG, at least 96 × 96 px."
    )
    primary_color = models.CharField(
        max_length=7, blank=True, validators=[HEX_COLOR], help_text="Main text and dark backgrounds, e.g. #172b46. Empty: the design's own."
    )
    secondary_color = models.CharField(
        max_length=7, blank=True, validators=[HEX_COLOR], help_text="Accent colour for highlights and buttons, e.g. #c5983c."
    )
    font_heading = models.CharField(
        max_length=60, blank=True, validators=[FONT_NAME], help_text="A Google Fonts family for headings, e.g. “Playfair Display”."
    )
    font_body = models.CharField(max_length=60, blank=True, validators=[FONT_NAME], help_text="A Google Fonts family for text, e.g. “Inter”.")

    # Social links (shown where the design has a place for them)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)
    youtube_url = models.URLField(blank=True)
    x_url = models.URLField("X (Twitter) URL", blank=True)

    # Marketing tags, added to every page when filled in
    gtm_id = models.CharField("Google Tag Manager ID", max_length=20, blank=True, help_text="e.g. GTM-ABC1234")
    ga4_id = models.CharField("Google Analytics 4 ID", max_length=20, blank=True, help_text="e.g. G-ABC123XYZ9")
    meta_pixel_id = models.CharField("Meta pixel ID", max_length=20, blank=True, help_text="Digits only.")

    tenant_area = "settings"  # Only builder admins change the contact details, branding and tags.
    blank_for_new_builder = (
        "phone_display", "phone_dial", "phone_international", "whatsapp_number", "address_line_1", "address_line_2",
        "street_address", "city", "postal_code", "email", "map_embed_url",
    )

    class Meta:
        verbose_name = "Contact & site settings"
        verbose_name_plural = "Contact & site settings"

    def __str__(self):
        return "Contact & site settings"

    @property
    def whatsapp_url(self):
        return f"https://wa.me/{self.whatsapp_number}"


class HomePage(SingletonModel):
    # Hero
    hero_eyebrow = models.CharField(max_length=80, default="The Signature Collection")
    hero_headline_line_1 = models.CharField(max_length=80, default="A legacy of")
    hero_headline_line_2 = models.CharField(max_length=80, default="living well.")
    hero_intro = models.CharField(
        max_length=200, default="Discover landmark residences and destinations by M3M India."
    )
    hero_link_label = models.CharField(max_length=60, default="Explore our projects")
    hero_caption_left = models.CharField(max_length=60, default="Gurugram · India")
    hero_caption_right = models.CharField(max_length=60, default="Artistic impression")
    hero_form_title = models.CharField(max_length=60, default="Enquire with us")
    hero_form_intro = models.CharField(
        max_length=160, default="Request a private call with our residences team."
    )

    # Projects
    projects_label = models.CharField(max_length=80, default="M3M projects · Delhi NCR")
    projects_title_line_1 = models.CharField(max_length=80, default="Landmarks across")
    projects_title_line_2 = models.CharField(max_length=80, default="Delhi NCR.")
    projects_intro = models.TextField(
        default=(
            "66 iconic projects across Gurugram, Delhi, Noida and Panipat, from delivered landmarks "
            "to the addresses now taking shape. Find the one that feels like yours."
        )
    )
    projects_facts = models.TextField(
        blank=True,
        default="66 | Iconic projects\n4 | Cities\n2,279K+ | Sq m delivered",
        help_text="Figures above the intro, one per line: figure | label. Leave empty to count the projects on this site.",
    )

    # Journey
    journey_label = models.CharField(max_length=80, default="Our Journey")
    journey_title_line_1 = models.CharField(max_length=80, default="A track record.")
    journey_title_line_2 = models.CharField(max_length=80, default="A way of thinking.")
    journey_summary = models.TextField(
        default=(
            "Since 2010, M3M India has grown around a clear belief: lasting places begin with trust, "
            "thoughtful design and a commitment to people. That belief continues to shape our growing "
            "collection of residential and commercial addresses in Noida."
        )
    )
    journey_link_url = models.URLField(default="https://m3mindia.com/our-story")
    journey_link_label = models.CharField(max_length=80, default="Discover our journey")
    journey_stats_note = models.CharField(
        max_length=120, default="Figures as published on the", blank=True
    )

    # News
    news_label = models.CharField(max_length=80, default="In the headlines")
    news_title_line_1 = models.CharField(max_length=80, default="M3M, as seen")
    news_title_line_2 = models.CharField(max_length=80, default="in the news.")
    news_intro = models.TextField(
        default="A selection of recent coverage from established business and real estate publications."
    )

    # Media gallery
    media_label = models.CharField(max_length=80, default="A closer look")
    media_title_line_1 = models.CharField(max_length=80, default="Spaces made")
    media_title_line_2 = models.CharField(max_length=80, default="to be experienced.")
    media_intro = models.TextField(
        default="Explore the details, destinations and everyday moments that shape the M3M point of view."
    )

    # Insights
    insights_label = models.CharField(max_length=80, default="Ideas & perspectives")
    insights_title = models.CharField(max_length=80, default="Insights from M3M")
    insights_intro = models.TextField(
        default="A closer look at the ideas, details and city stories behind each address."
    )

    # Guided journey
    guided_label = models.CharField(max_length=80, default="Your M3M edit")
    guided_title = models.CharField(max_length=120, default="Explore projects that feel right.")
    guided_intro = models.TextField(
        default="Choose what you’re looking for to discover a shortlist of M3M addresses."
    )

    # Contact
    contact_label = models.CharField(max_length=80, default="We’re here to help")
    contact_title_line_1 = models.CharField(max_length=80, default="Let’s find")
    contact_title_line_2 = models.CharField(max_length=80, default="your next address.")
    contact_intro = models.TextField(
        default=(
            "Tell us what you’re looking for. Our team can help you explore the right M3M project and "
            "answer your questions."
        )
    )
    contact_button_label = models.CharField(max_length=60, default="Speak with our team")
    contact_footer_tagline = models.CharField(
        max_length=120, default="Considered spaces. Personal conversations."
    )

    blank_for_new_builder = ("journey_link_url",)

    class Meta:
        verbose_name = "Homepage text"
        verbose_name_plural = "Homepage text"

    def __str__(self):
        return "Homepage text"

    @property
    def projects_fact_list(self):
        facts = []
        for line in self.projects_facts.splitlines():
            value, _, label = line.partition("|")
            if value.strip():
                facts.append((value.strip(), label.strip()))
        return facts


class HeroBanner(models.Model):
    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    image = ResizingImageField(upload_to=BuilderUploadTo("banners"), help_text="Wide landscape image, at least 2000px wide.")
    video = models.FileField(
        upload_to=BuilderUploadTo("banners"),
        blank=True,
        help_text="Optional silent MP4 loop. Plays in place of the image, which shows while it loads.",
    )
    alt_text = models.CharField(max_length=160, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField("Show on site", default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Hero banner"

    def __str__(self):
        return self.alt_text or f"Banner {self.pk}"


class Page(models.Model):
    """Simple text pages such as Privacy, Disclaimer and Compliance."""

    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    title = models.CharField(max_length=120)
    slug = models.SlugField(help_text="The page address, e.g. “privacy” → /privacy")
    body = models.TextField(help_text="Plain text. Leave a blank line between paragraphs.")
    meta_description = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        constraints = [models.UniqueConstraint(fields=["builder", "slug"], name="core_page_unique_slug_per_builder")]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("core:page", args=[self.slug])


class InnerPage(models.Model):
    """Banner, headings and SEO text for each page in the main menu."""

    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    class Key(models.TextChoices):
        PROJECTS = "projects", "Projects"
        JOURNEY = "journey", "Our Journey"
        MEDIA = "media", "Media"
        INSIGHTS = "insights", "Insights"
        CONTACT = "contact", "Contact Us"

    URL_NAMES = {
        Key.PROJECTS: "projects:list",
        Key.JOURNEY: "core:journey",
        Key.MEDIA: "core:media",
        Key.INSIGHTS: "insights",
        Key.CONTACT: "core:contact",
    }

    key = models.CharField(max_length=20, choices=Key.choices, editable=False)

    # Banner
    banner = ResizingImageField(upload_to=BuilderUploadTo("page-banners"), help_text="Wide image, at least 1600px wide.")
    banner_alt = models.CharField(max_length=160, blank=True)
    eyebrow = models.CharField(max_length=80, help_text="Small text above the title.")
    title = models.CharField(max_length=80)
    title_emphasis = models.CharField(max_length=80, blank=True, help_text="Second line, shown in accent colour.")
    intro = models.TextField(help_text="Short paragraph under the title.")

    # Form on the right of the banner
    form_title = models.CharField(max_length=80, blank=True, help_text="Leave empty to hide the form.")
    form_intro = models.CharField(max_length=200, blank=True, help_text="Short line under the form title.")

    # First section under the banner
    intro_label = models.CharField(max_length=80, blank=True)
    intro_heading = models.CharField(max_length=160, blank=True)
    intro_text = models.TextField(blank=True, help_text="Leave a blank line between paragraphs.")

    # Projects page only
    delivered_text = models.TextField("“Delivered Landmarks” text", blank=True)
    current_text = models.TextField("“Now Presenting” text", blank=True)
    upcoming_text = models.TextField("“On the Horizon” text", blank=True)

    # Our Journey page only
    quote_text = models.TextField(blank=True, help_text="Large quotation. Leave empty to hide.")
    quote_attribution = models.CharField(max_length=120, blank=True)

    # Contact page only
    next_steps = models.TextField(
        "“What happens next” cards",
        blank=True,
        help_text="Shown under the contact details, one card per line: title | short text. Leave empty to hide.",
    )
    info_image = ResizingImageField(
        upload_to=BuilderUploadTo("page-banners"), blank=True, help_text="Shown under the contact details, beside the form."
    )
    info_image_alt = models.CharField(max_length=160, blank=True)
    faq_image = ResizingImageField(
        upload_to=BuilderUploadTo("page-banners"), blank=True, help_text="Shown under the “Frequently asked” heading."
    )
    faq_image_alt = models.CharField(max_length=160, blank=True)

    seo_title = models.CharField(max_length=120, blank=True, help_text="Browser tab / Google title.")
    seo_description = models.CharField(max_length=300, blank=True, help_text="Defaults to the intro.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["builder", "key"], name="core_innerpage_unique_key_per_builder")]
        verbose_name = "Menu page (banner & text)"
        verbose_name_plural = "Menu pages (banners & text)"

    def __str__(self):
        return self.get_key_display()

    def get_absolute_url(self):
        return reverse(self.URL_NAMES[self.key])

    @classmethod
    def for_key(cls, builder, key):
        return cls.objects.for_builder(builder).filter(key=key).first()

    @property
    def form_source(self):
        """The enquiry source for the banner form (the Contact page already has its own "contact" form)."""
        return "contact_banner" if self.key == self.Key.CONTACT else self.key

    @property
    def next_step_list(self):
        steps = []
        for line in self.next_steps.splitlines():
            title, _, text = line.partition("|")
            if title.strip():
                steps.append((title.strip(), text.strip()))
        return steps


class FAQ(models.Model):
    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="+")
    tenant_path = "builder"

    objects = TenantQuerySet.as_manager()

    question = models.CharField(max_length=200)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField("Show on site", default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "FAQ (Contact page)"
        verbose_name_plural = "FAQs (Contact page)"

    def __str__(self):
        return self.question
