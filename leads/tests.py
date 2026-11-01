from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from leads import validation
from leads.models import Enquiry
from projects.models import Project
from tenants.models import Builder


class ValidationTests(TestCase):
    def test_names(self):
        for name in ["Asha Verma", "Rahul D'Souza", "Jean-Luc Picard", "Dr. A. Kumar", "José Ñúñez", "आशा वर्मा"]:
            self.assertEqual(validation.validate_name(name), "", name)
        for name in ["", "A", "123", "Asha  --Verma", "Asha_", "-Asha", "Asha-"]:
            self.assertNotEqual(validation.validate_name(name), "", name)

    def test_emails(self):
        for email in ["name@example.com", "a.b+c@sub.example.co.in", "x@xn--p1ai.xn--p1ai"]:
            self.assertEqual(validation.validate_email(email), "", email)
        for email in ["", "name", "name@", "@example.com", "a@b", "a@@b.com", "a..b@example.com", "a@-b.com"]:
            self.assertNotEqual(validation.validate_email(email), "", email)

    def test_phones(self):
        self.assertEqual(validation.parse_phone("98765 43210"), "+919876543210")
        self.assertEqual(validation.parse_phone("+44 7911 123456"), "+447911123456")
        for phone in ["", "12345", "9999999999", "+91 00000 00000"]:
            self.assertIsNone(validation.parse_phone(phone), phone)


@override_settings(LEAD_NOTIFICATION_EMAILS=["sales@example.com"])
class SubmitEnquiryTests(TestCase):
    url = reverse("submit_enquiry")

    def setUp(self):
        cache.clear()
        self.project = Project.objects.create(
            builder=Builder.objects.get(slug="m3m"),
            name="Test Tower", slug="test-tower", category="M3M", is_residential=True,
            offering="3 BHK", location="Sector 1", rera="RERA1", image="projects/x.jpg", summary="Test",
        )

    def post(self, **data):
        return self.client.post(self.url, data)

    def test_hero_enquiry_is_saved_and_emailed(self):
        response = self.post(
            source="hero", name="Asha Verma", phone="9876543210", email="asha@example.com",
            callTime="morning", utm_source="google", utm_campaign="launch",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.phone, "+919876543210")
        self.assertEqual(enquiry.utm_campaign, "launch")
        self.assertEqual(len(mail.outbox), 1)

    def test_billionaire_private_viewing(self):
        response = self.post(
            source="billionaire", name="Asha Verma", phone="+971501234567", email="asha@example.com",
            residence="Sky Villas", visit_date="2030-01-15", chauffeur="on", message="Evening, please.",
        )
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.source, Enquiry.Source.BILLIONAIRE)
        self.assertEqual(enquiry.phone, "+971501234567")
        self.assertEqual(
            enquiry.message,
            "Preferred residence: Sky Villas\nPreferred date: 15 Jan 2030\nChauffeur pickup requested\n\nEvening, please.",
        )

    def test_billionaire_invitation_details(self):
        response = self.post(
            source="billionaire", name="Asha Verma", phone="+971501234567", email="asha@example.com",
            residence="Signature Residences by ELIE SAAB", visit_mode="Virtual presentation", visit_date="2030-01-15",
            callTime="evening", guests="3", purpose="An investment",
        )
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.call_time, Enquiry.CallTime.EVENING)
        self.assertEqual(
            enquiry.message,
            "Preferred residence: Signature Residences by ELIE SAAB\nMeeting: Virtual presentation\n"
            "Preferred date: 15 Jan 2030\nConsidering it as: An investment\nGuests attending: 3",
        )

    def test_billionaire_rejects_an_unknown_time(self):
        response = self.post(
            source="billionaire", name="Asha Verma", phone="+971501234567", email="asha@example.com", callTime="midnight"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("callTime", response.json()["errors"])

    def test_ad_click_details_are_saved(self):
        self.post(
            source="hero", name="Asha Verma", phone="9876543210", email="asha@example.com", callTime="morning",
            utm_source="google", utm_medium="cpc", utm_campaign="noida-luxury", utm_content="ad-1",
            gclid="Cj0KCQ-test", matchtype="e", fbclid="", device="m", city="Noida",
            keyword="luxury flats noida", tbcli="TB-123",  # the old site's names
        )
        enquiry = Enquiry.objects.get()
        self.assertEqual(
            (enquiry.utm_term, enquiry.gclid, enquiry.matchtype, enquiry.tbclid, enquiry.device, enquiry.city),
            ("luxury flats noida", "Cj0KCQ-test", "e", "TB-123", "mobile", "Noida"),
        )

    def test_device_comes_from_the_browser_and_long_values_never_lose_a_lead(self):
        response = self.client.post(
            self.url,
            dict(source="hero", name="Asha Verma", phone="9876543210", email="asha@example.com", callTime="morning",
                 utm_campaign="x" * 500, gclid="g" * 600),
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148",
        )
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.device, "mobile")
        self.assertEqual((len(enquiry.utm_campaign), len(enquiry.gclid)), (120, 255))

    def test_brochure_needs_only_name_and_phone(self):
        response = self.post(source="brochure", name="Asha Verma", phone="9876543210")
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.email, "")
        self.assertEqual(enquiry.message, "Brochure download")

    def test_brochure_still_rejects_a_bad_phone(self):
        response = self.post(source="brochure", name="Asha Verma", phone="12")
        self.assertEqual(set(response.json()["errors"]), {"phone"})

    def test_popup_with_project(self):
        self.post(
            source="popup", name="Asha Verma", phone="9876543210", email="asha@example.com",
            callTime="evening", consent="on", project="test-tower",
        )
        self.assertEqual(Enquiry.objects.get().project, self.project)

    def test_guided_requires_its_own_fields(self):
        response = self.post(source="guided", phone="9876543210", email="a@example.com", consent="on")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"interest", "residency", "project"})

    def test_guided_enquiry(self):
        response = self.post(
            source="guided", interest="residential", residency="nri", project="test-tower",
            phone="+44 7911 123456", email="a@example.com", consent="on",
        )
        self.assertTrue(response.json()["ok"])
        self.assertEqual(Enquiry.objects.get().residency, "nri")

    def test_projects_page_form_needs_an_interest(self):
        response = self.post(source="projects", name="Asha Verma", phone="9876543210", email="a@example.com")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()["errors"]), {"interest"})

    def test_projects_page_form(self):
        response = self.post(
            source="projects", interest="commercial", name="Asha Verma", phone="9876543210", email="a@example.com",
        )
        self.assertTrue(response.json()["ok"])
        self.assertEqual(Enquiry.objects.get().interest, "commercial")

    def test_every_banner_form_needs_an_interest_but_no_consent(self):
        for source in Enquiry.BANNER_FORMS:
            response = self.post(source=source, name="Asha Verma", phone="9876543210", email="a@example.com")
            self.assertEqual(set(response.json()["errors"]), {"interest"}, source)

    def test_invalid_submission_returns_field_errors(self):
        response = self.post(source="popup", name="A", phone="1", email="x")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            set(response.json()["errors"]), {"name", "phone", "email", "callTime", "consent"}
        )
        self.assertFalse(Enquiry.objects.exists())

    def test_contact_page_enquiry_with_message(self):
        response = self.post(
            source="contact", name="Asha Verma", phone="9876543210", email="asha@example.com",
            callTime="flexible", consent="on", project="test-tower", message="Looking for a 3 BHK.",
        )
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.message, "Looking for a 3 BHK.")
        self.assertEqual(enquiry.project, self.project)

    def test_honeypot_is_silently_ignored(self):
        response = self.post(
            source="hero", name="Asha Verma", phone="9876543210", email="asha@example.com",
            callTime="morning", consent="on", website="spam.example",
        )
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Enquiry.objects.exists())

    @override_settings(LEAD_RATE_LIMIT_PER_HOUR=2)
    def test_rate_limit(self):
        data = dict(source="hero", name="Asha Verma", phone="9876543210", email="asha@example.com",
                    callTime="morning", consent="on")
        self.assertEqual(self.post(**data).status_code, 200)
        self.assertEqual(self.post(**data).status_code, 200)
        self.assertEqual(self.post(**data).status_code, 429)

    def test_csrf_is_enforced(self):
        client = self.client_class(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, {"source": "hero"}).status_code, 403)


@override_settings(LEAD_NOTIFICATION_EMAILS=[])
class LandingLeadTests(TestCase):
    """The ad landing page form: name, mobile, email and project type, with junk filtering."""

    url = reverse("submit_enquiry")

    def setUp(self):
        cache.clear()
        common = dict(builder=Builder.objects.get(slug="m3m"), category="M3M Jacob & Co.", location="Sector 97", rera="R1", image="projects/x.jpg", summary="S")
        self.residences = Project.objects.create(name="Residences", slug="res", is_residential=True, offering="3 BHK", **common)
        self.retail = Project.objects.create(name="Retail", slug="retail", is_commercial=True, offering="Shops", **common)

    def post(self, **overrides):
        data = dict(
            source="landing", name="Asha Verma", phone="9876543210", email="asha@gmail.com",
            interest="residential", project="res", message="Requested: Unlock the brochure", utm_source="facebook",
        )
        data.update(overrides)
        return self.client.post(self.url, data)

    def test_valid_lead_is_saved_with_request_and_campaign(self):
        response = self.post()
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get()
        self.assertEqual((enquiry.source, enquiry.interest, enquiry.project), ("landing", "residential", self.residences))
        self.assertEqual(enquiry.message, "Requested: Unlock the brochure")
        self.assertEqual(enquiry.utm_source, "facebook")

    def test_lead_for_names_the_website_the_lead_came_from(self):
        cullinan = Project.objects.create(
            builder=Builder.objects.get(slug="m3m"),
            name="Cullinan", slug="cullinan", category="M3M The Cullinan", is_residential=True, offering="4 BHK",
            location="Sector 94", rera="R2", image="projects/x.jpg", summary="S",
        )
        trump = Project.objects.create(
            builder=Builder.objects.get(slug="m3m"),
            name="Trump", slug="trump", category="M3M Trump Tower", is_residential=True, offering="4 BHK",
            location="Sector 94", rera="R3", image="projects/x.jpg", summary="S",
        )
        self.post()
        self.post(project="cullinan", phone="9876543211")
        self.post(project="trump", phone="9876543212")
        self.post(source="billionaire", phone="+971501234567")
        self.post(source="popup", project="trump", phone="9876543213", callTime="evening", consent="on")
        self.post(source="hero", phone="9876543214", callTime="morning")
        self.assertEqual(
            list(Enquiry.objects.order_by("created_at").values_list("lead_for", flat=True)),
            ["jacob", "cullinan", "trump", "billionaire", "core", "core"],
        )
        # The main website's popup still records the project the customer asked about.
        self.assertEqual(Enquiry.objects.get(phone="+919876543213").project, trump)
        self.assertTrue(cullinan.enquiries.exists())

    def test_commercial_lead_is_filed_against_the_commercial_project(self):
        self.post(interest="commercial", project="retail")
        self.assertEqual(Enquiry.objects.get().project, self.retail)

    def test_junk_is_rejected(self):
        for field, value in [
            ("name", "Test"), ("name", "asdf"), ("name", "aaaa"), ("name", "12"),
            ("email", "x@mailinator.com"), ("email", "a@example.com"), ("email", "not-an-email"),
            ("phone", "9999999999"), ("phone", "12345"), ("interest", ""), ("interest", "villa"),
        ]:
            response = self.post(**{field: value})
            self.assertEqual(response.status_code, 400, (field, value))
            self.assertIn(field, response.json()["errors"], (field, value))
        self.assertFalse(Enquiry.objects.exists())

    def test_email_is_required(self):
        self.assertIn("email", self.post(email="").json()["errors"])

    def test_repeat_submission_updates_the_same_lead(self):
        self.post()
        self.post(message="Requested: Get the price list")
        enquiry = Enquiry.objects.get()
        self.assertIn("Unlock the brochure", enquiry.message)
        self.assertIn("Get the price list", enquiry.message)

    def test_honeypot_is_silently_dropped(self):
        self.assertTrue(self.post(website="http://spam.example").json()["ok"])
        self.assertFalse(Enquiry.objects.exists())
