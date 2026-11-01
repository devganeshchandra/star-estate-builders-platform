import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import SiteSettings
from leads.forms import EnquiryForm, client_ip
from leads.models import Enquiry

logger = logging.getLogger(__name__)


def _rate_limited(request):
    key = f"enquiry-rate:{client_ip(request)}"
    count = cache.get_or_set(key, 0, 60 * 60)
    if count >= settings.LEAD_RATE_LIMIT_PER_HOUR:
        return True
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, 60 * 60)
    return False


@require_POST
def submit_enquiry(request):
    if request.builder is None:
        raise Http404
    form = EnquiryForm(request.POST, builder=request.builder, domain=request.domain)
    if not form.is_valid():
        errors = {field: messages[0] for field, messages in form.errors.items()}
        return JsonResponse({"ok": False, "errors": errors}, status=400)

    message = SiteSettings.load(request.builder).enquiry_success_message
    if form.is_spam():
        return JsonResponse({"ok": True, "message": message})
    if _rate_limited(request):
        return JsonResponse(
            {
                "ok": False,
                "message": "We’ve received several requests from this connection. Please call or WhatsApp our team.",
            },
            status=429,
        )

    # Ad landing pages: the same number asking again within a day adds to the existing lead
    # instead of creating a duplicate for the sales team to call twice.
    data = form.cleaned_data
    if data["source"] == Enquiry.Source.LANDING:
        recent = Enquiry.objects.for_builder(request.builder).filter(
            phone=data["phone"], project=data["project_obj"], created_at__gte=timezone.now() - timedelta(days=1)
        ).first()
        if recent:
            request_note = form.full_message()
            if request_note and request_note not in recent.message:
                recent.message = "\n".join(filter(None, [recent.message, request_note]))
                recent.save(update_fields=["message", "updated_at"])
            return JsonResponse({"ok": True, "message": message})

    enquiry = form.save(request)
    _notify(request, enquiry)
    return JsonResponse({"ok": True, "message": message})


def recipients(builder):
    """The builder's own lead inbox(es), plus the platform-wide copy (LEAD_NOTIFICATION_EMAILS), if any."""
    own = [email.strip() for email in SiteSettings.load(builder).lead_notification_emails.split(",") if email.strip()]
    return list(dict.fromkeys(own + settings.LEAD_NOTIFICATION_EMAILS))


def _notify(request, enquiry):
    to = recipients(enquiry.builder)
    if not to:
        return
    admin_url = request.build_absolute_uri(reverse("admin:leads_enquiry_change", args=[enquiry.pk]))
    lines = [
        f"Builder: {enquiry.builder} · {enquiry.source_domain or '—'}",
        f"Landing page: {enquiry.landing_page or '—'}",
        f"Lead for: {enquiry.get_lead_for_display()}",
        f"Source: {enquiry.get_source_display()}",
        f"Project: {enquiry.project or '—'}",
        f"Name: {enquiry.name or '—'}",
        f"Phone: {enquiry.phone}",
        f"Email: {enquiry.email}",
        f"Preferred call time: {enquiry.get_call_time_display() or '—'}",
        f"Interest: {enquiry.get_interest_display() or '—'}",
        f"Based in: {enquiry.get_residency_display() or '—'}",
        f"Message: {enquiry.message or '—'}",
        f"Campaign: {enquiry.utm_source or '—'} / {enquiry.utm_medium or '—'} / {enquiry.utm_campaign or '—'}",
        f"Keyword: {enquiry.utm_term or '—'}{f' ({enquiry.matchtype})' if enquiry.matchtype else ''}",
        f"Device: {enquiry.device or '—'} · City: {enquiry.city or '—'}",
        f"Ad click: {'Google' if enquiry.gclid else 'Meta' if enquiry.fbclid else 'Taboola' if enquiry.tbclid else '—'}",
        f"Page: {enquiry.page_url or '—'}",
        "",
        f"Open in admin: {admin_url}",
    ]
    try:
        send_mail(
            subject=f"New lead – {enquiry.builder}{f' · {enquiry.project}' if enquiry.project else ''}",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=to,
        )
    except Exception:
        logger.exception("Could not send enquiry notification for enquiry %s", enquiry.pk)
