from django import forms
from django.db import models
from django.urls import reverse
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from core.admin import SingletonAdmin
from projects import landing
from projects.models import (
    BillionaireBlockPage,
    BillionaireResidence,
    LandingImage,
    LandingItem,
    LandingPage,
    LandingText,
    Project,
    ProjectConfiguration,
    ProjectHighlight,
    ProjectImage,
)
from tenants.admin_scoping import TenantScopedAdmin


def _change_url(obj):
    return reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk]) if obj else ""


def _main_page(project):
    return project.landing_pages.filter(is_default=True).first() if project and project.pk else None


class ProjectHighlightInline(TabularInline):
    model = ProjectHighlight
    extra = 0
    tab = True


class ProjectConfigurationInline(TabularInline):
    model = ProjectConfiguration
    extra = 0
    tab = True


class ProjectImageInline(StackedInline):
    model = ProjectImage
    extra = 0
    tab = True


@admin.register(Project)
class ProjectAdmin(TenantScopedAdmin, ModelAdmin):
    list_display = ["thumbnail", "name", "status", "is_featured", "location", "order", "is_published", "enquiry_count"]
    list_display_links = ["thumbnail", "name"]
    list_editable = ["status", "is_featured", "order", "is_published"]
    list_filter = ["status", "is_published", "is_featured", "category", "is_residential", "is_commercial"]
    list_select_related = ["builder"]
    search_fields = ["name", "category", "location", "rera"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [ProjectHighlightInline, ProjectConfigurationInline, ProjectImageInline]
    readonly_fields = ["where_to_edit"]
    fieldsets = [
        (
            "Project card",
            {
                "fields": [
                    "builder",
                    ("name", "slug"),
                    "category",
                    ("is_residential", "is_commercial"),
                    "offering",
                    ("location", "city"),
                    "rera",
                    "image",
                    "summary",
                    ("status", "timeline_note"),
                    ("is_featured", "order", "is_published"),
                ]
            },
        ),
        (
            "Landing page",
            {
                "fields": ["overview_label", "headline", "description", "brochure", "map_embed_url"],
                "description": "Highlights, floor plans and the gallery are in the tabs above.",
            },
        ),
        ("Search engines", {"fields": ["seo_title", "seo_description"], "classes": ["collapse"]}),
    ]

    def get_fieldsets(self, request, obj=None):
        if _main_page(obj):
            # Its page is an ad landing page: the standard page fields and tabs are not shown on the site.
            return [
                ("Where this project’s page is edited", {"fields": ["where_to_edit"]}),
                self.fieldsets[0],
                ("Search engines", {"fields": ["seo_title", "seo_description"], "classes": ["collapse"]}),
            ]
        return self.fieldsets

    def get_inlines(self, request, obj):
        return [] if _main_page(obj) else self.inlines

    @admin.display(description="Page content")
    def where_to_edit(self, obj):
        return format_html(
            "This project has its own landing page. Every text, picture and list on it, including its phone, "
            "WhatsApp and RERA block, is edited in <a href=\"{}\" style=\"font-weight:700;text-decoration:underline\">"
            "{} → all page content</a>. Here you edit the project card (name, RERA number, picture, stage) that "
            "appears on the Projects page and in enquiries. <a href=\"{}\" target=\"_blank\">View the page ↗</a>",
            _change_url(_main_page(obj)), obj.name, obj.get_absolute_url(),
        )

    @admin.display(description="")
    def thumbnail(self, obj):
        if not obj.image:
            return ""
        return format_html('<img src="{}" style="width:72px;height:48px;object-fit:cover;border-radius:4px">', obj.image.url)

    @admin.display(description="Enquiries")
    def enquiry_count(self, obj):
        return obj.enquiries.count()


class BillionaireResidenceInline(StackedInline):
    model = BillionaireResidence
    extra = 0
    tab = True
    fields = [("name", "order", "is_published"), "tagline", ("size", "configuration"), "features", ("image", "image_alt"), "floor_plan"]


@admin.register(BillionaireBlockPage)
class BillionaireBlockPageAdmin(SingletonAdmin):
    # Only the fields the live page and homepage teaser use. Every other text, image and list on
    # /billionaire-block is under “Ad landing pages → Billionaire Block”.
    inlines = [BillionaireResidenceInline]
    readonly_fields = ["where_to_edit"]
    fieldsets = [
        ("Where each part of the page is edited", {"fields": ["where_to_edit"]}),
        (
            "Hero (top of the page)",
            {
                "fields": ["hero_video", "hero_image", "hero_image_alt", "eyebrow", "title", "tagline"],
                "description": "The “Residence types” tab only fills the “Preferred residence” choices in the "
                "viewing form.",
            },
        ),
        (
            "Homepage teaser",
            {
                "fields": [
                    "teaser_label",
                    "teaser_heading",
                    "teaser_text",
                    "teaser_button",
                    "about_facts",
                    "about_image",
                    "building_image",
                    "building_image_2",
                ],
                "description": "The Billionaire Block band on the homepage, just after the projects section. "
                "It also uses the hero video and image. The three smaller pictures around it are "
                "About image, Building image and Building image 2.",
            },
        ),
        (
            "Private viewing form",
            {
                "fields": [
                    "form_label",
                    "form_heading",
                    "form_intro",
                    "viewing_steps",
                    "form_success_title",
                    "form_success_text",
                    "form_note",
                ]
            },
        ),
        ("Brochure", {"fields": ["brochure", "brochure_heading", "brochure_text"]}),
        ("Footer", {"fields": ["rera_number", "footer_disclaimer"]}),
        ("Search engines & sharing", {"fields": ["seo_title", "seo_description"]}),
    ]

    create_missing = False  # Only builders that have this page.

    @admin.display(description="This page")
    def where_to_edit(self, obj):
        return format_html(
            "Here: the banner at the top, the private viewing form and its residence choices, the brochure, the "
            "RERA line in the footer and the homepage band. Every other section (the story, community, amenities, "
            "towers, location, timeline, sources) is in <a href=\"{}\" style=\"font-weight:700;text-decoration:underline\">"
            "Billionaire Block → all other content</a>. <a href=\"/billionaire-block\" target=\"_blank\">View the page ↗</a>",
            _change_url(landing.builder_page(obj.builder, landing.BILLIONAIRE)),
        )


def _thumbnail(image):
    if not image:
        return ""
    return format_html('<img src="{}" style="width:72px;height:48px;object-fit:cover;border-radius:4px">', image.url)


def _list_field(slug=None):
    return forms.ChoiceField(label="List", choices=[("", "Choose a list")] + landing.list_choices(slug))


class LandingTextInline(TabularInline):
    model = LandingText
    extra = 0
    tab = True
    fields = ["section", "label", "value"]
    readonly_fields = ["section", "label"]
    can_delete = False
    formfield_overrides = {models.TextField: {"widget": forms.Textarea(attrs={"rows": 2})}}

    def has_add_permission(self, request, obj=None):
        return False  # Each text is a fixed place on the page, created by projects/landing.py.


class LandingImageInline(TabularInline):
    model = LandingImage
    extra = 0
    tab = True
    fields = ["section", "label", "preview", "image", "alt"]
    readonly_fields = ["section", "label", "preview"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Now")
    def preview(self, obj):
        return _thumbnail(obj.image)


class LandingItemInline(StackedInline):
    model = LandingItem
    extra = 0
    tab = True
    collapsible = True
    verbose_name_plural = "Lists"
    fields = [
        ("list_key", "order", "is_published"),
        ("title", "subtitle"),
        ("value", "group", "link"),
        "text",
        ("image", "image_alt"),
    ]

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        formset.form.base_fields["list_key"] = _list_field(obj.template if obj else None)
        return formset


class LandingPageForm(forms.ModelForm):
    template = forms.ChoiceField(
        label="Design", choices=[], help_text="The page design. Its starting texts, pictures and lists are added for you to edit."
    )

    class Meta:
        model = LandingPage
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].choices = landing.template_choices()


@admin.register(LandingPage)
class LandingPageAdmin(TenantScopedAdmin, ModelAdmin):
    list_display = ["name", "builder", "project", "address", "is_default", "is_published", "related"]
    list_filter = ["project", "is_published", "is_default"]
    list_select_related = ["builder", "project"]
    search_fields = ["name", "slug", "project__name"]
    inlines = [LandingTextInline, LandingImageInline, LandingItemInline]
    readonly_fields = ["how_to_edit", "design"]

    @admin.display(description="Design")
    def design(self, obj):
        module = landing.PAGES.get(obj.template)
        return module.NAME if module else obj.template or "—"

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs["form"] = LandingPageForm
        return super().get_form(request, obj, **kwargs)

    def get_inlines(self, request, obj):
        return self.inlines if obj else []

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            landing.fill_page(obj)

    class Media:
        js = ["admin/landing-finder.js"]

    @admin.display(description="Address on the website")
    def address(self, obj):
        if obj.template == landing.WEBSITE_TEXTS:
            return "Every page (header, footer, popup, small headings)"
        url = obj.get_absolute_url()
        return format_html('<a href="{}" target="_blank">{} ↗</a>', url, url)

    @admin.display(description="Also edited in")
    def related(self, obj):
        return self._related_links(obj) or "—"

    def _related_links(self, obj):
        if obj.template == landing.BILLIONAIRE:
            return format_html('<a href="{}">Billionaire Block: banner, form & RERA</a>',
                               reverse("admin:projects_billionaireblockpage_changelist"))
        if obj.project_id:
            enquiries = reverse("admin:leads_enquiry_changelist") + f"?landing_page__id__exact={obj.pk}"
            return format_html('<a href="{}">Project card (name, RERA no., picture)</a> · <a href="{}">Enquiries</a>',
                               _change_url(obj.project), enquiries)
        return ""

    @admin.display(description="How to edit this page")
    def how_to_edit(self, obj):
        if obj is None or obj.pk is None:
            return ""
        view = format_html('<a href="{}" target="_blank" style="font-weight:700">View the page ↗</a>',
                           obj.get_absolute_url())
        related = self._related_links(obj)
        steps = mark_safe(
            "<ol style=\"margin:6px 0 0 18px;list-style:decimal;line-height:1.7\">"
            "<li><strong>Texts</strong> tab: every heading, line and button, grouped by section in page order.</li>"
            "<li><strong>Pictures</strong> tab: every single picture; upload a new file to replace one.</li>"
            "<li><strong>Lists</strong> tab: repeating items (slides, amenities, places, menu links, FAQs…). Add, "
            "remove, reorder with “Order”, or untick “Show on site”.</li>"
            "<li>Not sure where something is? Type a few words you see on the website into "
            "<strong>Find on this page</strong> just above the tabs.</li>"
            "<li>Put <em>*stars*</em> around words in a heading to show them in italics. Click <strong>Save</strong> "
            "at the bottom, then view the page.</li></ol>"
        )
        extra = format_html(" · Also edited in: {}", related) if related else ""
        return format_html("{}{}{}", view, extra, steps)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return [(None, {"fields": ["builder", "project", "name", "slug", "template", "is_default", "is_published"]})]
        fieldsets = [(None, {"fields": ["how_to_edit", "name"]})]
        if obj.project_id:  # Billionaire Block and the website texts have no page SEO of their own here.
            fieldsets += [
                ("Page", {"fields": ["project", "slug", "design", "is_default", "is_published"]}),
                (
                    "Search engines & sharing",
                    {"fields": ["seo_title", "seo_description", "share_title", "share_description", "share_image"]},
                ),
            ]
        fieldsets.append(
            (
                "How each list uses its fields",
                {
                    "fields": [],
                    "classes": ["collapse"],
                    "description": format_html_join("", "<p><strong>{}</strong>: {}</p>", landing.list_help(obj.template)),
                },
            )
        )
        return fieldsets

    def has_delete_permission(self, request, obj=None):
        return False  # Untick “Show on site” instead: leads keep pointing at the page.


class LandingItemForm(forms.ModelForm):
    list_key = _list_field()

    class Meta:
        model = LandingItem
        fields = "__all__"


@admin.register(LandingItem)
class LandingItemAdmin(TenantScopedAdmin, ModelAdmin):
    form = LandingItemForm
    list_display = ["thumbnail", "title", "list_name", "page", "order", "is_published"]
    list_display_links = ["thumbnail", "title"]
    list_editable = ["order", "is_published"]
    list_filter = ["page", "list_key", "is_published"]
    search_fields = ["title", "subtitle", "text"]
    fields = [
        ("page", "list_key"),
        ("title", "subtitle"),
        ("value", "group", "link"),
        "text",
        ("image", "image_alt"),
        ("order", "is_published"),
    ]

    @admin.display(description="")
    def thumbnail(self, obj):
        return _thumbnail(obj.image)

    @admin.display(description="List", ordering="list_key")
    def list_name(self, obj):
        return dict(landing.list_choices(obj.page.template)).get(obj.list_key, obj.list_key)
