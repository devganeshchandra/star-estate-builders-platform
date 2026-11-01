from django import forms

from leads import validation
from leads.models import Enquiry
from projects.models import LandingPage, Project

CONSENT_ERROR = "Please confirm that we may contact you about this enquiry."
GUIDED_CONSENT_ERROR = "Please confirm that we may contact you about this request."


class EnquiryForm(forms.Form):
    """Handles every website form; `source` decides which fields are required.

    The builder comes from the website the form was sent on (request.builder), never from the form itself, and
    the project and landing page are looked up within that builder only: a form cannot file a lead against
    another builder's project, whatever it posts.
    """

    def __init__(self, *args, builder, domain=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.builder = builder
        self.domain = domain

    source = forms.ChoiceField(choices=Enquiry.Source.choices)
    name = forms.CharField(max_length=80, required=False)
    phone = forms.CharField(max_length=25, required=False)
    email = forms.CharField(max_length=254, required=False)
    callTime = forms.CharField(max_length=20, required=False)
    interest = forms.CharField(max_length=20, required=False)
    residency = forms.CharField(max_length=20, required=False)
    project = forms.SlugField(max_length=120, required=False)
    # The landing page the form is on (its id), when it is on one.
    landing = forms.IntegerField(min_value=1, required=False)
    consent = forms.BooleanField(required=False)
    message = forms.CharField(max_length=2000, required=False)
    # Billionaire Block private viewing: folded into the message for the sales team.
    residence = forms.CharField(max_length=80, required=False)
    visit_date = forms.DateField(required=False)
    visit_mode = forms.CharField(max_length=80, required=False)
    purpose = forms.CharField(max_length=80, required=False)
    guests = forms.IntegerField(min_value=1, max_value=12, required=False)
    chauffeur = forms.BooleanField(required=False)
    page_url = forms.CharField(max_length=1000, required=False)
    # Honeypot: real visitors never see or fill this field.
    website = forms.CharField(required=False)

    # Campaign and ad click details. No length limit here: an over-long value is trimmed to fit its column
    # (TRACKING) rather than losing the lead. The old site's names are accepted too (TRACKING_ALIASES).
    utm_source = forms.CharField(required=False)
    utm_medium = forms.CharField(required=False)
    utm_campaign = forms.CharField(required=False)
    utm_term = forms.CharField(required=False)
    utm_content = forms.CharField(required=False)
    gclid = forms.CharField(required=False)
    matchtype = forms.CharField(required=False)
    fbclid = forms.CharField(required=False)
    tbclid = forms.CharField(required=False)
    device = forms.CharField(required=False)
    city = forms.CharField(required=False)
    keyword = forms.CharField(required=False)
    tblci = forms.CharField(required=False)
    tbcli = forms.CharField(required=False)

    def clean(self):
        data = super().clean()
        source = data.get("source")
        if not source:
            return data

        errors = {}
        if source in {Enquiry.Source.HERO, Enquiry.Source.POPUP, Enquiry.Source.CONTACT}:
            if data.get("callTime") not in Enquiry.CallTime.values:
                errors["callTime"] = "Choose a preferred time for your call."
        if source == Enquiry.Source.LANDING:
            if message := validation.validate_real_name(data.get("name")):
                errors["name"] = message
            if data.get("interest") not in Enquiry.Interest.values:
                errors["interest"] = "Choose residential or commercial."
            if message := validation.validate_lead_email(data.get("email")):
                errors["email"] = message
        elif source != Enquiry.Source.GUIDED:
            if message := validation.validate_name(data.get("name")):
                errors["name"] = message
        # Optional on the other forms (the Jacob & Co. private line, the Billionaire Block invitation).
        if data.get("callTime") and data["callTime"] not in Enquiry.CallTime.values:
            errors.setdefault("callTime", "Choose a preferred time for your call.")
        if source in Enquiry.BANNER_FORMS and data.get("interest") not in Enquiry.Interest.values:
            errors["interest"] = "Choose residential or commercial."

        if source == Enquiry.Source.GUIDED:
            if data.get("interest") not in Enquiry.Interest.values:
                errors["interest"] = "Choose the direction that feels right for you."
            if data.get("residency") not in Enquiry.Residency.values:
                errors["residency"] = "Choose the option that best describes you."
            if not data.get("project"):
                errors["project"] = f"Choose a project for your personal {self.builder.name} edit."

        phone = validation.parse_phone(data.get("phone"))
        if not phone:
            errors["phone"] = validation.PHONE_ERROR
        # The brochure form asks only for a name and phone number.
        if source not in {Enquiry.Source.BROCHURE, Enquiry.Source.LANDING} or (
            source == Enquiry.Source.BROCHURE and data.get("email")
        ):
            if message := validation.validate_email(data.get("email")):
                errors["email"] = message
        # These forms have no consent checkbox: sending them is the request to be contacted.
        # The landing page states the contact terms beside its submit button.
        no_consent = {
            Enquiry.Source.HERO,
            Enquiry.Source.BILLIONAIRE,
            Enquiry.Source.BROCHURE,
            Enquiry.Source.LANDING,
            *Enquiry.BANNER_FORMS,
        }
        if source not in no_consent and not data.get("consent"):
            errors["consent"] = GUIDED_CONSENT_ERROR if source == Enquiry.Source.GUIDED else CONSENT_ERROR

        project = None
        if data.get("project"):
            project = Project.objects.for_builder(self.builder).published().filter(slug=data["project"]).first()
            if project is None:
                errors["project"] = f"Choose a project for your personal {self.builder.name} edit."

        page = None
        if data.get("landing"):
            page = LandingPage.objects.for_builder(self.builder).filter(pk=data["landing"], is_published=True).first()
            if page is None or (project is not None and page.project_id not in (None, project.pk)):
                errors["landing"] = "This page is no longer available. Please reload it and try again."
        elif source == Enquiry.Source.LANDING and project is not None:
            page = project.landing_pages.filter(is_default=True).first()

        for field, message in errors.items():
            self.add_error(field, message)

        data["phone"] = phone
        data["project_obj"] = project
        data["landing_obj"] = page
        return data

    def full_message(self):
        data = self.cleaned_data
        lines = []
        if data.get("residence"):
            lines.append(f"Preferred residence: {data['residence']}")
        if data.get("visit_mode"):
            lines.append(f"Meeting: {data['visit_mode']}")
        if data.get("visit_date"):
            lines.append(f"Preferred date: {data['visit_date']:%d %b %Y}")
        if data.get("purpose"):
            lines.append(f"Considering it as: {data['purpose']}")
        if data.get("guests"):
            lines.append(f"Guests attending: {data['guests']}")
        if data.get("chauffeur"):
            lines.append("Chauffeur pickup requested")
        if data["source"] == Enquiry.Source.BROCHURE:
            lines.append("Brochure download")
        message = (data.get("message") or "").strip()
        return "\n".join(lines + ([""] if lines and message else []) + ([message] if message else []))

    def is_spam(self):
        return bool(self.cleaned_data.get("website"))

    def save(self, request):
        data = self.cleaned_data
        return Enquiry.objects.create(
            builder=self.builder,
            source_domain=self.domain.domain if self.domain else "",
            landing_page=data["landing_obj"],
            lead_for=Enquiry.lead_for_of(data["source"], data["project_obj"]),
            source=data["source"],
            project=data["project_obj"],
            name=validation.normalize_name(data.get("name")),
            phone=data["phone"],
            email=(data.get("email") or "").strip(),
            call_time=data.get("callTime") or "",
            interest=data.get("interest") or "",
            residency=data.get("residency") or "",
            consent=True,
            message=self.full_message(),
            page_url=(data.get("page_url") or request.headers.get("referer", ""))[:1000],
            ip_address=client_ip(request),
            user_agent=request.headers.get("user-agent", "")[:500],
            **self.tracking(request),
        )

    def tracking(self, request):
        """The campaign and ad click fields, trimmed to their columns, with the old names accepted and the
        device worked out from the browser when the ad link does not give it."""
        data = self.cleaned_data
        values = {field: (data.get(field) or "").strip() for field in TRACKING}
        for field, aliases in TRACKING_ALIASES.items():
            values[field] = values[field] or next((data[a].strip() for a in aliases if data.get(a)), "")
        values["device"] = DEVICES.get(values["device"].lower(), values["device"]) or device_from(
            request.headers.get("user-agent", "")
        )
        return {field: value[: TRACKING[field]] for field, value in values.items()}


# Tracking fields and their column lengths (leads/models.py).
TRACKING = {
    "utm_source": 120, "utm_medium": 120, "utm_campaign": 120, "utm_term": 120, "utm_content": 120,
    "gclid": 255, "matchtype": 20, "fbclid": 255, "tbclid": 255, "device": 20, "city": 100,
}
# Names the old website and ad templates used: {keyword} for the search term, Taboola's tblci (or tbcli).
TRACKING_ALIASES = {"utm_term": ["keyword"], "tbclid": ["tblci", "tbcli"]}
# Google Ads {device}: m, t or c.
DEVICES = {"m": "mobile", "t": "tablet", "c": "desktop", "computer": "desktop"}


def device_from(user_agent):
    agent = user_agent.lower()
    if not agent:
        return ""
    if "ipad" in agent or "tablet" in agent or ("android" in agent and "mobile" not in agent):
        return "tablet"
    if "mobi" in agent or "iphone" in agent or "android" in agent:
        return "mobile"
    return "desktop"


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return ip or None
