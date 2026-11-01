from django.core.exceptions import ValidationError
from django.db import models

from tenants.query import TenantQuerySet


class Enquiry(models.Model):
    class Source(models.TextChoices):
        HERO = "hero", "Homepage hero form"
        POPUP = "popup", "Enquiry popup"
        GUIDED = "guided", "Project discovery (homepage)"
        CONTACT = "contact", "Contact page"
        BILLIONAIRE = "billionaire", "Billionaire Block page"
        BROCHURE = "brochure", "Billionaire Block brochure"
        LANDING = "landing", "Project landing page (ads)"
        PROJECTS = "projects", "Projects page form"
        JOURNEY = "journey", "Our Journey page form"
        MEDIA = "media", "Media page form"
        INSIGHTS = "insights", "Insights page form"
        CONTACT_BANNER = "contact_banner", "Contact page banner form"

    # The short forms on the menu-page banners: interest, name, mobile and email.
    BANNER_FORMS = {Source.PROJECTS, Source.JOURNEY, Source.MEDIA, Source.INSIGHTS, Source.CONTACT_BANNER}

    class CallTime(models.TextChoices):
        MORNING = "morning", "Morning · 9 AM–12 PM"
        AFTERNOON = "afternoon", "Afternoon · 12–3 PM"
        EVENING = "evening", "Evening · 3–6 PM"
        FLEXIBLE = "flexible", "Flexible"

    class Interest(models.TextChoices):
        RESIDENTIAL = "residential", "Residential"
        COMMERCIAL = "commercial", "Commercial"

    class Residency(models.TextChoices):
        INDIA = "india", "India"
        NRI = "nri", "Overseas (NRI)"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        SITE_VISIT = "site_visit", "Site visit booked"
        CLOSED_WON = "won", "Closed – booked"
        CLOSED_LOST = "lost", "Closed – not interested"
        SPAM = "spam", "Spam / invalid"

    class LeadFor(models.TextChoices):
        """Which website the lead came from, so the sales team knows what the customer is interested in."""

        JACOB = "jacob", "M3M Jacob & Co."
        CULLINAN = "cullinan", "M3M The Cullinan"
        TRUMP = "trump", "M3M Trump Tower"
        BILLIONAIRE = "billionaire", "Billionaire Block"
        CORE = "core", "M3M Core (main website)"

    builder = models.ForeignKey("tenants.Builder", on_delete=models.PROTECT, related_name="enquiries")
    tenant_path = "builder"
    tenant_area = "leads"
    landing_page = models.ForeignKey(
        "projects.LandingPage", null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries"
    )
    source_domain = models.CharField(
        max_length=253, blank=True, help_text="The website address the lead was sent from, e.g. m3mhome.in."
    )

    objects = TenantQuerySet.as_manager()

    lead_for = models.CharField(
        "Lead for", max_length=20, choices=LeadFor.choices, default=LeadFor.CORE,
        help_text="Set from the form the lead came through: a project landing page, Billionaire Block or the main website.",
    )
    source = models.CharField(max_length=20, choices=Source.choices)
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries"
    )
    name = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=25, help_text="Stored in international format.")
    email = models.EmailField(max_length=254, blank=True)
    call_time = models.CharField(max_length=20, choices=CallTime.choices, blank=True)
    interest = models.CharField(max_length=20, choices=Interest.choices, blank=True)
    residency = models.CharField(max_length=20, choices=Residency.choices, blank=True)
    consent = models.BooleanField(default=False)
    message = models.TextField(blank=True, max_length=2000)

    page_url = models.URLField(max_length=1000, blank=True)
    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)
    utm_term = models.CharField(max_length=120, blank=True)
    utm_content = models.CharField(max_length=120, blank=True)
    # Ad click details, from the link the visitor arrived by (static/js/site.js keeps them for the visit).
    gclid = models.CharField("Google Ads click ID (gclid)", max_length=255, blank=True)
    matchtype = models.CharField(
        "Google Ads match type", max_length=20, blank=True, help_text="e = exact, p = phrase, b = broad"
    )
    fbclid = models.CharField("Meta click ID (fbclid)", max_length=255, blank=True)
    tbclid = models.CharField("Taboola click ID (tblci)", max_length=255, blank=True)
    device = models.CharField(
        max_length=20, blank=True, help_text="mobile, tablet or desktop: from the ad link, else from the browser"
    )
    city = models.CharField(max_length=100, blank=True, help_text="From the ad link or form, when given")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    assigned_to = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_enquiries"
    )
    notes = models.TextField(blank=True, help_text="Internal notes from the sales team.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Enquiries"
        # Indexes for the queries that grow with the number of leads: the newest-first list, the sales team's
        # status and source filters, and the repeat-lead check by phone (leads/views.py).
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["lead_for", "-created_at"], name="leads_enquiry_lead_for"),
            models.Index(fields=["-created_at"], name="leads_enquiry_newest"),
            models.Index(fields=["source", "-created_at"], name="leads_enquiry_source"),
            models.Index(fields=["phone", "-created_at"], name="leads_enquiry_phone"),
            models.Index(fields=["email"], name="leads_enquiry_email"),
        ]

    def __str__(self):
        return f"{self.name or self.email} · {self.get_lead_for_display()}"

    def clean(self):
        try:
            self.check_ownership()
        except ValueError as error:
            raise ValidationError(str(error)) from error

    def check_ownership(self):
        """A lead's project, landing page and assigned salesperson must all belong to the lead's builder."""
        if self.project_id and self.project.builder_id != self.builder_id:
            raise ValueError("The project belongs to another builder.")
        if self.landing_page_id and self.landing_page.builder_id != self.builder_id:
            raise ValueError("The landing page belongs to another builder.")
        if self.landing_page_id and self.project_id and self.landing_page.project_id not in (None, self.project_id):
            raise ValueError("The landing page belongs to another project.")
        if self.assigned_to_id and not self.assigned_to.is_superuser and not self.assigned_to.builder_memberships.filter(
            builder_id=self.builder_id, is_active=True
        ).exists():
            raise ValueError("The salesperson does not work for this builder.")

    def save(self, *args, **kwargs):
        self.check_ownership()
        super().save(*args, **kwargs)

    @classmethod
    def lead_for_of(cls, source, project):
        """Billionaire Block's forms, a project landing page (by its project), else the main website."""
        if source in {cls.Source.BILLIONAIRE, cls.Source.BROCHURE}:
            return cls.LeadFor.BILLIONAIRE
        if source == cls.Source.LANDING and project is not None:
            category = project.category.lower()
            for value, keyword in [(cls.LeadFor.JACOB, "jacob"), (cls.LeadFor.CULLINAN, "cullinan"), (cls.LeadFor.TRUMP, "trump")]:
                if keyword in category:
                    return value
        return cls.LeadFor.CORE
