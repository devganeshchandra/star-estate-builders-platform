"""Multi-builder hosting: domain resolution, data isolation between builders, and admin roles."""

import shutil
import tempfile
from io import BytesIO, StringIO

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from content.models import Insight, Publication
from core.models import HomePage, SiteSettings
from leads.models import Enquiry
from projects.models import LandingPage, Project
from tenants.models import Builder, BuilderMembership, Domain, normalize_domain
from tenants.provisioning import provision

MEDIA_ROOT = tempfile.mkdtemp()
HOSTS = ["testserver", "m3mhome.in", "acehome.in", "xyzhome.in", "unknown.in", "admin.localhost", ".localhost"]


def make_project(builder, slug, name=None, **extra):
    values = dict(
        name=name or slug.title(), category=f"{builder.name} collection", is_residential=True, offering="4 BHK",
        location="Sector 94, Noida", rera="RERA-1", image="projects/x.jpg", summary="A project.",
    )
    values.update(extra)
    return Project.objects.create(builder=builder, slug=slug, **values)


def make_page(project, slug, template="m3m-trump-tower-noida", **extra):
    page = LandingPage.objects.create(project=project, slug=slug, name=f"{project.name} {slug}", template=template, **extra)
    from projects import landing

    landing.fill_page(page)
    return page


@override_settings(
    ALLOWED_HOSTS=HOSTS, PLATFORM_ADMIN_HOSTS=["admin.localhost"], LEAD_NOTIFICATION_EMAILS=[], MEDIA_ROOT=MEDIA_ROOT
)
class TenantTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.m3m = Builder.objects.get(slug="m3m")
        Domain.objects.filter(domain="m3mhome.in").update(is_verified=True)
        provision(cls.m3m)
        cls.ace = Builder.objects.create(name="ACE", slug="ace")
        Domain.objects.create(builder=cls.ace, domain="acehome.in", is_primary=True, is_verified=True)
        provision(cls.ace)
        cls.xyz = Builder.objects.create(name="XYZ", slug="xyz")
        Domain.objects.create(builder=cls.xyz, domain="xyzhome.in", is_primary=True, is_verified=True)
        provision(cls.xyz)
        # The same project, under the same address, for two builders.
        cls.m3m_jacob = make_project(cls.m3m, "jacob", "Jacob & Co. Residences")
        cls.ace_jacob = make_project(cls.ace, "jacob", "Jacob & Co. Residences")
        cls.ace_only = make_project(cls.ace, "ace-skyline", "ACE Skyline")

    def setUp(self):
        cache.clear()

    def get(self, host, path="/"):
        return self.client.get(path, HTTP_HOST=host)

    def post_lead(self, host, **data):
        values = dict(source="popup", name="Asha Verma", phone="9876543210", email="asha@gmail.com",
                      callTime="evening", consent="on")
        values.update(data)
        return self.client.post(reverse("submit_enquiry"), values, HTTP_HOST=host)


class DomainResolutionTests(TenantTestCase):
    def test_each_domain_shows_its_own_builder(self):
        for host, name in [("m3mhome.in", "M3M India"), ("acehome.in", "ACE"), ("xyzhome.in", "XYZ")]:
            response = self.get(host)
            self.assertEqual(response.status_code, 200, host)
            self.assertEqual(response.wsgi_request.builder.name, name if name != "M3M India" else "M3M")
            self.assertContains(response, f'<meta property="og:site_name" content="{name}">', html=False)

    def test_host_names_are_normalised(self):
        self.assertEqual(normalize_domain("HTTPS://WWW.AceHome.in:8000/path"), "www.acehome.in")
        self.assertEqual(normalize_domain("acehome.in."), "acehome.in")
        self.assertEqual(normalize_domain("bad_host!.in"), "")
        self.assertEqual(self.client.get("/", HTTP_HOST="ACEHOME.IN").wsgi_request.builder, self.ace)
        domain = Domain.objects.create(builder=self.ace, domain=" WWW.AceHome.IN ")
        self.assertEqual(domain.domain, "www.acehome.in")

    def test_unknown_domain_gets_a_plain_404_without_any_builder_data(self):
        response = self.get("unknown.in")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content, b"Site not found.")

    def test_host_outside_allowed_hosts_is_refused(self):
        self.assertEqual(self.get("evil.example").status_code, 400)

    def test_unverified_and_inactive_domains_are_not_served(self):
        Domain.objects.filter(domain="acehome.in").update(is_verified=False)
        cache.clear()
        self.assertEqual(self.get("acehome.in").status_code, 404)
        Domain.objects.filter(domain="acehome.in").update(is_verified=True, is_active=False)
        cache.clear()
        self.assertEqual(self.get("acehome.in").status_code, 404)

    def test_inactive_builder_is_offline_at_once(self):
        self.assertEqual(self.get("acehome.in").status_code, 200)
        self.ace.is_active = False
        self.ace.save()  # Clears the cached domain → builder mapping.
        self.assertEqual(self.get("acehome.in").status_code, 404)
        self.assertEqual(self.get("m3mhome.in").status_code, 200)

    def test_no_url_parameter_can_switch_builder(self):
        response = self.client.get("/projects/ace-skyline?builder=ace&builder_id=%d" % self.ace.pk, HTTP_HOST="m3mhome.in")
        self.assertEqual(response.status_code, 404)

    def test_health_check_and_admin_host_need_no_builder(self):
        self.assertEqual(self.get("unknown.in", "/healthz").status_code, 200)
        self.assertEqual(self.get("admin.localhost", "/admin/login/").status_code, 200)
        self.assertEqual(self.get("admin.localhost", "/").status_code, 404)

    def test_canonical_address_is_the_builders_primary_domain(self):
        response = self.get("acehome.in", "/projects")
        self.assertContains(response, '<link rel="canonical" href="https://acehome.in/projects">', html=False)

    def test_local_domains_command(self):
        with override_settings(DEBUG=True):
            call_command("add_local_domains", stdout=StringIO())
        self.assertEqual(Domain.objects.get(domain="ace.localhost").builder, self.ace)
        self.assertEqual(Domain.objects.get(domain="localhost").builder, self.m3m)
        self.assertEqual(self.get("ace.localhost").wsgi_request.builder, self.ace)


class IsolationTests(TenantTestCase):
    def test_same_project_slug_for_two_builders_but_not_twice_for_one(self):
        self.assertEqual(self.get("m3mhome.in", "/projects/jacob").context["project"], self.m3m_jacob)
        self.assertEqual(self.get("acehome.in", "/projects/jacob").context["project"], self.ace_jacob)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_project(self.ace, "jacob")

    def test_a_builder_cannot_reach_another_builders_project(self):
        self.assertEqual(self.get("m3mhome.in", "/projects/ace-skyline").status_code, 404)
        self.assertNotContains(self.get("m3mhome.in", "/projects"), "ACE Skyline")
        self.assertContains(self.get("acehome.in", "/projects"), "ACE Skyline")

    def test_several_landing_pages_per_project_each_isolated(self):
        main = make_page(self.ace_jacob, "jacob", is_default=True)
        campaign = make_page(self.ace_jacob, "diwali-offer", template="m3m-the-cullinan-residential")
        self.assertTemplateUsed(self.get("acehome.in", "/projects/jacob"), "projects/landing/m3m-trump-tower-noida.html")
        response = self.get("acehome.in", "/projects/jacob/diwali-offer")
        self.assertTemplateUsed(response, "projects/landing/m3m-the-cullinan-residential.html")
        self.assertEqual(response.context["landing"], campaign)
        # M3M's Jacob project has no such page, and ACE's page is not reachable through M3M.
        self.assertEqual(self.get("m3mhome.in", "/projects/jacob/diwali-offer").status_code, 404)
        self.assertNotEqual(self.get("m3mhome.in", "/projects/jacob").context.get("landing"), main)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_page(self.ace_jacob, "diwali-offer")

    def test_landing_page_must_use_its_projects_builder(self):
        with self.assertRaises(ValueError):
            LandingPage.objects.create(builder=self.m3m, project=self.ace_jacob, slug="x", name="x", template="m3m-trump-tower-noida")

    def test_articles_and_legal_pages_are_per_builder(self):
        Insight.objects.create(builder=self.ace, title="ACE news", slug="news", category="News", image="i.jpg",
                               description="d", body="b")
        Insight.objects.create(builder=self.m3m, title="M3M news", slug="news", category="News", image="i.jpg",
                               description="d", body="b")
        self.assertContains(self.get("acehome.in", "/insights/news"), "ACE news")
        self.assertContains(self.get("m3mhome.in", "/insights/news"), "M3M news")
        self.assertEqual(self.get("xyzhome.in", "/insights/news").status_code, 404)

    def test_new_builder_starts_with_none_of_another_builders_details(self):
        ace = SiteSettings.load(self.ace)
        self.assertEqual((ace.site_name, ace.phone_display, ace.whatsapp_number, str(ace.logo)), ("ACE", "", "", ""))
        response = self.get("acehome.in")
        self.assertNotContains(response, "M3M")
        self.assertNotContains(response, SiteSettings.load(self.m3m).phone_display or "1800 123 3333")
        self.assertIn("ACE", HomePage.load(self.ace).hero_intro)

    def test_sitemap_lists_only_the_builders_own_pages(self):
        ace = self.get("acehome.in", "/sitemap.xml").content.decode()
        m3m = self.get("m3mhome.in", "/sitemap.xml").content.decode()
        self.assertIn("http://acehome.in/projects/ace-skyline", ace)
        self.assertNotIn("ace-skyline", m3m)
        self.assertNotIn("acehome.in", m3m)


class CrossTenantLeadTests(TenantTestCase):
    def test_lead_belongs_to_the_website_it_was_sent_on(self):
        page = make_page(self.ace_jacob, "jacob", is_default=True)
        response = self.post_lead("acehome.in", source="landing", project="jacob", landing=page.pk, interest="residential")
        self.assertEqual(response.status_code, 200, response.content)
        lead = Enquiry.objects.get()
        self.assertEqual((lead.builder, lead.project, lead.landing_page, lead.source_domain),
                         (self.ace, self.ace_jacob, page, "acehome.in"))

    def test_form_cannot_file_a_lead_against_another_builders_project(self):
        response = self.post_lead("m3mhome.in", project="ace-skyline")
        self.assertEqual(response.status_code, 400)
        self.assertIn("project", response.json()["errors"])
        self.assertFalse(Enquiry.objects.exists())

    def test_form_cannot_name_another_builders_landing_page(self):
        ace_page = make_page(self.ace_jacob, "jacob", is_default=True)
        response = self.post_lead("m3mhome.in", source="landing", project="jacob", landing=ace_page.pk, interest="residential")
        self.assertEqual(response.status_code, 400)
        self.assertIn("landing", response.json()["errors"])
        self.assertFalse(Enquiry.objects.exists())

    def test_same_slug_resolves_to_the_senders_own_project(self):
        self.post_lead("m3mhome.in", project="jacob")
        self.post_lead("acehome.in", project="jacob", phone="9876543211")
        self.assertEqual(Enquiry.objects.get(builder=self.m3m).project, self.m3m_jacob)
        self.assertEqual(Enquiry.objects.get(builder=self.ace).project, self.ace_jacob)

    def test_model_refuses_mismatched_builder(self):
        with self.assertRaises(ValueError):
            Enquiry.objects.create(builder=self.m3m, project=self.ace_jacob, source="popup", phone="+919876543210")

    def test_repeat_landing_leads_merge_only_within_a_builder(self):
        make_page(self.m3m_jacob, "jacob", is_default=True)
        make_page(self.ace_jacob, "jacob", is_default=True)
        for host in ("m3mhome.in", "acehome.in", "acehome.in"):
            self.post_lead(host, source="landing", project="jacob", interest="residential")
        self.assertEqual(Enquiry.objects.filter(builder=self.m3m).count(), 1)
        self.assertEqual(Enquiry.objects.filter(builder=self.ace).count(), 1)

    def test_notifications_go_to_the_builders_own_inbox(self):
        settings_row = SiteSettings.load(self.ace)
        settings_row.lead_notification_emails = "sales@acehome.in"
        settings_row.save()
        self.post_lead("acehome.in")
        self.post_lead("m3mhome.in", phone="9876543211")
        self.assertEqual([m.to for m in mail.outbox], [["sales@acehome.in"]])


class AdminRoleTests(TenantTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.m3m_lead = Enquiry.objects.create(builder=cls.m3m, source="popup", name="Mira M3M", phone="+919876543210")
        cls.ace_lead = Enquiry.objects.create(builder=cls.ace, source="popup", name="Arun ACE", phone="+919876543211")

    def login(self, role, builder=None):
        user = User.objects.create_user(f"{role}-user", password="pass", is_staff=True)
        BuilderMembership.objects.create(user=user, builder=builder or self.ace, role=role)
        self.client.force_login(user)
        return user

    def test_builder_admin_sees_only_their_builder(self):
        self.login(BuilderMembership.Role.BUILDER_ADMIN)
        leads = self.client.get("/admin/leads/enquiry/", HTTP_HOST="acehome.in")
        self.assertContains(leads, "Arun ACE")
        self.assertNotContains(leads, "Mira M3M")
        projects = self.client.get("/admin/projects/project/", HTTP_HOST="acehome.in")
        self.assertContains(projects, "ACE Skyline")
        self.assertNotContains(projects, f"/admin/projects/project/{self.m3m_jacob.pk}/change/")

    def test_changing_the_id_in_the_address_does_not_open_another_builders_record(self):
        self.login(BuilderMembership.Role.BUILDER_ADMIN)
        for url in [f"/admin/leads/enquiry/{self.m3m_lead.pk}/change/",
                    f"/admin/projects/project/{self.m3m_jacob.pk}/change/",
                    f"/admin/core/sitesettings/{SiteSettings.load(self.m3m).pk}/change/"]:
            response = self.client.get(url, HTTP_HOST="acehome.in")
            self.assertNotEqual(response.status_code, 200, url)
            self.assertNotContains(response, "Mira M3M", status_code=response.status_code)

    def test_builder_admin_cannot_create_records_for_another_builder(self):
        self.login(BuilderMembership.Role.BUILDER_ADMIN)
        buffer = BytesIO()
        Image.new("RGB", (40, 20), "navy").save(buffer, "JPEG")
        data = dict(builder=self.m3m.pk, name="Sneaky", slug="sneaky", category="C", offering="O", location="L",
                    city="Noida", rera="R", summary="S", status="current", headline="H", overview_label="A", order=0,
                    image=SimpleUploadedFile("p.jpg", buffer.getvalue(), content_type="image/jpeg"))
        for prefix in ("highlights", "configurations", "gallery"):
            data.update({f"{prefix}-TOTAL_FORMS": 0, f"{prefix}-INITIAL_FORMS": 0})
        response = self.client.post("/admin/projects/project/add/", data, HTTP_HOST="acehome.in")
        self.assertEqual(response.status_code, 302)
        # The posted builder is ignored: someone working for ACE can only create ACE records.
        self.assertEqual(Project.objects.get(slug="sneaky").builder, self.ace)
        self.assertTrue(Project.objects.get(slug="sneaky").image.name.startswith("builders/ace/projects/"))

    def test_related_choices_from_another_builder_are_rejected(self):
        self.login(BuilderMembership.Role.BUILDER_ADMIN)
        m3m_pub = Publication.objects.create(builder=self.m3m, name="M3M Times", logo="p.png")
        response = self.client.post("/admin/content/pressitem/add/", dict(
            publication=m3m_pub.pk, title="T", published_on="2026-01-01", summary="S", article_url="https://x.in", order=0,
        ), HTTP_HOST="acehome.in")
        self.assertEqual(response.status_code, 200)  # Form shown again with an error
        self.assertContains(response, "Select a valid choice")

    def test_marketing_manager_manages_content_but_not_leads(self):
        self.login(BuilderMembership.Role.MARKETING)
        self.assertEqual(self.client.get("/admin/projects/project/").status_code, 200)
        self.assertEqual(self.client.get("/admin/leads/enquiry/").status_code, 403)

    def test_sales_sees_only_leads_assigned_to_them(self):
        user = self.login(BuilderMembership.Role.SALES)
        other = Enquiry.objects.create(builder=self.ace, source="popup", name="Other Lead", phone="+919876543212")
        Enquiry.objects.filter(pk=self.ace_lead.pk).update(assigned_to=user)
        response = self.client.get("/admin/leads/enquiry/")
        self.assertContains(response, "Arun ACE")
        self.assertNotContains(response, other.name)
        self.assertEqual(self.client.get("/admin/projects/project/").status_code, 403)

    def test_staff_without_a_membership_see_no_builder_data(self):
        user = User.objects.create_user("nobody", password="pass", is_staff=True)
        user.user_permissions.set(__import__("django.contrib.auth.models", fromlist=["Permission"]).Permission.objects.all())
        self.client.force_login(user)
        self.assertEqual(self.client.get("/admin/leads/enquiry/").status_code, 403)

    def test_salesperson_of_another_builder_cannot_be_assigned(self):
        m3m_sales = User.objects.create_user("m3m-sales", is_staff=True)
        BuilderMembership.objects.create(user=m3m_sales, builder=self.m3m, role=BuilderMembership.Role.SALES)
        self.ace_lead.assigned_to = m3m_sales
        with self.assertRaises(ValueError):
            self.ace_lead.save()

    def test_superuser_sees_every_builder(self):
        self.client.force_login(User.objects.create_superuser("root", "r@example.com", "pass"))
        leads = self.client.get("/admin/leads/enquiry/")
        self.assertContains(leads, "Arun ACE")
        self.assertContains(leads, "Mira M3M")
        self.assertEqual(self.client.get("/admin/tenants/builder/").status_code, 200)
        self.assertEqual(self.client.get(f"/admin/?builder={self.ace.slug}").status_code, 200)

    def test_only_superusers_manage_builders_and_domains(self):
        self.login(BuilderMembership.Role.BUILDER_ADMIN)
        self.assertEqual(self.client.get("/admin/tenants/builder/").status_code, 403)
        self.assertEqual(self.client.get("/admin/tenants/domain/").status_code, 403)

    def test_new_landing_page_from_the_admin_gets_its_designs_content(self):
        self.login(BuilderMembership.Role.MARKETING)
        response = self.client.post("/admin/projects/landingpage/add/", dict(
            project=self.ace_jacob.pk, name="Jacob launch", slug="launch", template="m3m-jacob-co-residences",
            is_published="on",
        ), HTTP_HOST="acehome.in")
        self.assertEqual(response.status_code, 302, response.content[:2000])
        page = LandingPage.objects.get(slug="launch")
        self.assertEqual(page.builder, self.ace)
        self.assertTrue(page.texts.exists())
        self.assertTrue(all(i.image.name.startswith("builders/ace/") for i in page.images.exclude(image="")))
        self.assertEqual(self.get("acehome.in", "/projects/jacob/launch").status_code, 200)

    def test_integrity_check_finds_nothing_wrong(self):
        out = StringIO()
        call_command("check_tenant_integrity", stdout=out)
        self.assertIn("Cross-builder links: 0", out.getvalue())
