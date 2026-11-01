import csv

from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeDateFilter

from leads.models import Enquiry
from tenants.admin_scoping import TenantScopedAdmin

SUBMITTED_FIELDS = [
    "builder",
    "source_domain",
    "landing_page",
    "lead_for",
    "source",
    "project",
    "name",
    "phone",
    "email",
    "call_time",
    "interest",
    "residency",
    "consent",
    "message",
    "page_url",
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "matchtype",
    "fbclid",
    "tbclid",
    "device",
    "city",
    "ip_address",
    "user_agent",
    "created_at",
]


@admin.register(Enquiry)
class EnquiryAdmin(TenantScopedAdmin, ModelAdmin):
    list_display = [
        "created_at", "builder", "lead_for", "name", "phone", "email", "project", "landing_page", "source", "call_time",
        "status", "assigned_to",
    ]
    list_display_links = ["created_at", "name"]
    list_editable = ["status", "assigned_to"]
    list_filter = [
        "lead_for", "status", "source", "project", "landing_page", "source_domain", "residency", ("created_at", RangeDateFilter), "utm_source", "utm_campaign", "device",
    ]
    list_filter_submit = True
    search_fields = ["name", "phone", "email", "notes", "utm_campaign", "city", "gclid", "fbclid", "tbclid"]
    list_select_related = ["builder", "project", "landing_page", "assigned_to"]
    readonly_fields = SUBMITTED_FIELDS + ["updated_at"]
    date_hierarchy = "created_at"
    actions = ["export_csv", "mark_contacted"]
    fieldsets = [
        ("Follow-up", {"fields": ["status", "assigned_to", "notes"]}),
        (
            "What the visitor submitted",
            {"fields": ["builder", "source_domain", "landing_page", "lead_for", "created_at", "source", "project", "name", "phone", "email", "call_time", "interest", "residency", "consent", "message"]},
        ),
        (
            "Campaign & tracking",
            {
                "fields": [
                    "page_url",
                    ("utm_source", "utm_medium"),
                    ("utm_campaign", "utm_term"),
                    "utm_content",
                    ("gclid", "matchtype"),
                    "fbclid",
                    "tbclid",
                    ("device", "city"),
                    ("ip_address", "updated_at"),
                    "user_agent",
                ]
            },
        ),
    ]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Export selected to Excel (CSV)")
    def export_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"enquiries-{timezone.localdate():%Y-%m-%d}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("﻿")  # So Excel opens UTF-8 correctly.
        writer = csv.writer(response)
        columns = ["created_at", "status", "assigned_to", "notes"] + [f for f in SUBMITTED_FIELDS if f != "created_at"]
        writer.writerow([Enquiry._meta.get_field(c).verbose_name.title() for c in columns])
        for enquiry in queryset.select_related("builder", "project", "landing_page", "assigned_to"):
            row = []
            for column in columns:
                display = getattr(enquiry, f"get_{column}_display", None)
                value = display() if display else getattr(enquiry, column)
                if column == "created_at":
                    value = timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
                row.append("" if value is None else str(value))
            writer.writerow(row)
        return response

    @admin.action(description="Mark selected as contacted")
    def mark_contacted(self, request, queryset):
        updated = queryset.update(status=Enquiry.Status.CONTACTED)
        self.message_user(request, f"{updated} enquiries marked as contacted.")
