import shutil
import tempfile
from io import BytesIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from content.models import Insight, Video
from core.models import HeroBanner, HomePage, InnerPage, Page, SiteSettings
from leads.models import Enquiry
from projects.models import BillionaireBlockPage, LandingItem, LandingPage, LandingText, Project
from tenants.models import Builder, BuilderMembership

MEDIA_ROOT = tempfile.mkdtemp()


def m3m():
    return Builder.objects.get(slug="m3m")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", verbosity=0)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()

    def test_homepage_renders_seeded_content(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A legacy of")
        self.assertContains(response, "M3M Trump Tower Noida")
        self.assertContains(response, "Moneycontrol")
        self.assertContains(response, "Wellness woven into the everyday")
        self.assertContains(response, 'class="project-card"', count=3)
        self.assertContains(response, "Explore all 9 projects")
        # Live figures beside the section headings, the journey card and the single-screen finder.
        self.assertContains(response, "<strong data-count-up>66</strong><span>Iconic projects</span>", html=False)
        self.assertContains(response, "Landmarks across")
        self.assertContains(response, "M3M India at a glance")
        self.assertContains(response, "Projects delivered")
        self.assertContains(response, 'class="finder-project"', count=9)
        self.assertContains(response, "Send me my M3M edit")

    def test_homepage_text_is_editable(self):
        page = HomePage.load(m3m())
        page.hero_headline_line_1 = "A brand new"
        page.save()
        self.assertContains(self.client.get("/"), "A brand new")

    def test_projects_figures_fall_back_to_live_counts(self):
        page = HomePage.load(m3m())
        page.projects_facts = ""
        page.save()
        self.assertContains(self.client.get("/"), "<strong data-count-up>9</strong><span>Addresses</span>", html=False)

    def test_contact_settings_are_used_everywhere(self):
        settings = SiteSettings.load(m3m())
        settings.phone_display = "1800 000 0000"
        settings.whatsapp_number = "911234567890"
        settings.save()
        response = self.client.get("/")
        self.assertContains(response, "1800 000 0000")
        self.assertContains(response, "https://wa.me/911234567890")

    def test_project_page(self):
        # A project without an ad landing page uses the standard project page.
        response = self.client.get("/projects/m3m-the-line-pentsuites")
        self.assertContains(response, "UPRERAPRJ246070")
        self.assertContains(response, "<title>M3M The Line Pentsuites | M3M India</title>", html=False)

    def test_unpublished_project_is_hidden(self):
        Project.objects.filter(slug="m3m-trump-tower-noida").update(is_published=False)
        self.assertEqual(self.client.get("/projects/m3m-trump-tower-noida").status_code, 404)
        self.assertNotContains(self.client.get("/"), "M3M Trump Tower Noida")

    def test_website_map_and_editing_from_the_site(self):
        admin = User.objects.create_superuser("admin", "a@example.com", "pass")
        self.client.force_login(admin)
        response = self.client.get("/admin/")
        self.assertContains(response, "Website map")
        for slug in ("m3m-jacob-co-residences", "m3m-the-cullinan-residential", "m3m-trump-tower-noida", "billionaire-block"):
            page = LandingPage.objects.get(slug=slug)
            self.assertContains(response, f"/admin/projects/landingpage/{page.pk}/change/", html=False)
        # Staff see “Edit this page”, opening the screens that edit that page; visitors never do.
        response = self.client.get("/projects/m3m-trump-tower-noida")
        self.assertContains(response, "Edit this page")
        trump = LandingPage.objects.get(slug="m3m-trump-tower-noida")
        self.assertContains(response, f"/admin/projects/landingpage/{trump.pk}/change/", html=False)
        self.client.logout()
        self.assertNotContains(self.client.get("/projects/m3m-trump-tower-noida"), "Edit this page")

    def test_shared_texts_and_menu_are_edited_in_the_admin(self):
        texts = LandingPage.objects.get(slug="website-texts")
        LandingText.objects.filter(page=texts, key="cta_title").update(value="Your *next home.*")
        LandingText.objects.filter(page=texts, key="footer_rights").update(value="Every right reserved.")
        response = self.client.get("/our-journey")
        self.assertContains(response, "Your <em>next home.</em>", html=False)
        self.assertContains(response, "Every right reserved.")
        # The menu: rename a link, add one, and hide a project from the dropdown.
        texts.items.filter(list_key="menu", link="/our-journey").update(title="Our Story")
        texts.items.create(list_key="menu", title="Careers", link="/careers", order=99)
        texts.items.filter(list_key="project_menu", link="/projects/m3m-trump-tower-noida").update(is_published=False)
        response = self.client.get("/")
        self.assertContains(response, "Our Story")
        self.assertContains(response, 'href="/careers"', html=False)
        self.assertNotContains(response, "Sector 94 · 4 &amp; 5 BHK")

    def test_website_editors_can_run_the_site_but_not_manage_users(self):
        from django.contrib.auth.models import Group

        editor = User.objects.create_user("editor", "e@example.com", "pass", is_staff=True)
        editor.groups.add(Group.objects.get(name="Website editors"))
        # Staff see only the builders they work for: the editor works on M3M.
        BuilderMembership.objects.create(user=editor, builder=m3m(), role=BuilderMembership.Role.BUILDER_ADMIN)
        self.client.force_login(editor)
        trump = LandingPage.objects.get(slug="m3m-trump-tower-noida")
        for url in ["/admin/", f"/admin/projects/landingpage/{trump.pk}/change/", "/admin/projects/project/add/",
                    "/admin/content/insight/add/", f"/admin/core/sitesettings/{SiteSettings.load(m3m()).pk}/change/",
                    "/admin/leads/enquiry/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/admin/auth/user/").status_code, 403)

    def test_project_landing_sections(self):
        project = Project.objects.get(slug="m3m-the-line-pentsuites")
        project.highlights.create(title="Golf course views")
        project.configurations.create(unit_type="4 BHK", size="4,800 sq. ft.")
        response = self.client.get(project.get_absolute_url())
        self.assertContains(response, "Golf course views")
        self.assertContains(response, "4,800 sq. ft.")
        self.assertContains(response, "Price on request")

    def test_pages(self):
        self.assertEqual(self.client.get("/disclaimer").status_code, 200)
        self.assertEqual(self.client.get("/privacy").status_code, 404)
        Page.objects.filter(slug="privacy").update(is_published=True)
        self.assertEqual(self.client.get("/privacy").status_code, 200)

    def test_seo_files(self):
        self.assertContains(self.client.get("/sitemap.xml"), "/projects/m3m-trump-tower-noida")
        self.assertContains(self.client.get("/sitemap.xml"), "/billionaire-block")
        self.assertContains(self.client.get("/robots.txt"), "Sitemap:")

    def test_admin_screens_load(self):
        admin = User.objects.create_superuser("admin", "a@example.com", "pass")
        self.client.force_login(admin)
        for url in [
            "/admin/",
            "/admin/leads/enquiry/",
            "/admin/projects/project/",
            "/admin/projects/project/add/",
            f"/admin/projects/project/{Project.objects.first().pk}/change/",
            f"/admin/core/homepage/{HomePage.load(m3m()).pk}/change/",
            f"/admin/projects/billionaireblockpage/{BillionaireBlockPage.objects.get().pk}/change/",
            "/admin/projects/landingpage/",
            "/admin/projects/landingitem/",
            "/admin/projects/landingitem/add/",
            f"/admin/projects/landingitem/{LandingItem.objects.first().pk}/change/",
            *(f"/admin/projects/landingpage/{page.pk}/change/" for page in LandingPage.objects.all()),
            f"/admin/core/sitesettings/{SiteSettings.load(m3m()).pk}/change/",
            "/admin/core/herobanner/",
            "/admin/core/page/",
            "/admin/content/pressitem/",
            "/admin/content/mediaimage/",
            "/admin/content/insight/",
            "/admin/content/journeyprinciple/",
            "/admin/content/journeystat/",
            "/admin/content/milestone/",
            "/admin/content/video/",
            "/admin/core/faq/",
            "/admin/core/innerpage/",
            f"/admin/core/innerpage/{InnerPage.objects.get(key='projects').pk}/change/",
            f"/admin/core/innerpage/{InnerPage.objects.get(key='journey').pk}/change/",
            f"/admin/content/insight/{Insight.objects.first().pk}/change/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_billionaire_block_page(self):
        response = self.client.get("/billionaire-block")
        self.assertContains(
            response, "<title>M3M Billionaire Block, Sector 111 Gurugram | ELIE SAAB Residences</title>", html=False
        )
        self.assertContains(response, '"@type": "RealEstateListing"', html=False)
        # The research story, in order, from the plan to the sources.
        html = response.content.decode()
        order = [
            "What exactly is", "Signature Residences <em>by ELIE SAAB", "A residence <em>tailored", "What type of society is",
            "What amenities are they", "What type of towers, blocks and", "broader", "Location &amp;",
            "Launch timeline, investment", "Sources for",
        ]
        positions = [html.index(heading) for heading in order]
        self.assertEqual(positions, sorted(positions))
        # The four facts are tabs, each with its own picture; the acre facts count up.
        self.assertContains(response, "data-bbx-tab", count=4, html=False)
        self.assertContains(response, '<span data-count="170">170</span> acres', html=False)
        # Only confirmed facts: no unconfirmed township acreage, and the HRERA registration is shown.
        self.assertNotContains(response, "250 acres")
        self.assertContains(response, "GGM/992/724/2025/95")
        self.assertContains(response, 'href="https://haryanarera.gov.in/"', html=False)
        self.assertNotContains(response, "Approvals &amp; RERA")
        self.assertContains(response, "Wrap-around decks and private jacuzzis")
        self.assertContains(response, "data-bbx-spot", count=5, html=False)  # The room, and its four gold points.
        self.assertContains(response, 'style="left: 22%; top: 56%"', html=False)
        self.assertContains(response, "data-bbx-acc", count=8, html=False)  # The accordion, and its seven panels.
        self.assertContains(response, "data-bbx-dest", count=5, html=False)
        self.assertContains(
            response,
            "https://www.google.com/maps/dir/?api=1&amp;origin=Sector%20111%2C%20Gurugram%2C%20Haryana"
            "&amp;destination=Indira%20Gandhi%20International%20Airport%2C%20New%20Delhi",
            html=False,
        )
        self.assertContains(response, "bbx-press__featured", html=False)
        self.assertContains(response, "₹3,500 cr")
        self.assertContains(response, "https://haryanarera.gov.in/", html=False)
        for unverified in ("Sky Villas", "The Penthouse", "Helipad", "Bowling alley", "bb-club__card"):
            self.assertNotContains(response, unverified)
        self.assertContains(response, "Request Invitation")
        for field in ('name="visit_mode"', 'name="callTime"', 'name="guests"', 'name="purpose"', 'name="residence"'):
            self.assertContains(response, field, html=False)
        self.assertContains(response, 'name="source" value="billionaire"', html=False)
        self.assertContains(response, 'name="source" value="brochure"', html=False)
        self.assertContains(response, "billionaire-block/hero")

    def test_billionaire_block_is_highlighted_in_the_site_menu(self):
        response = self.client.get("/")
        self.assertContains(response, "desktop-nav__link--featured", html=False)

    def test_jacob_co_uses_its_ad_landing_page(self):
        response = self.client.get("/projects/m3m-jacob-co-residences")
        self.assertTemplateUsed(response, "projects/landing/m3m-jacob-co-residences.html")
        # Six forms: hero, private line and viewing pass, plus the popup's three rotating styles; all send landing leads.
        self.assertContains(response, 'name="source" value="landing"', count=6, html=False)
        for field, count in (('data-validate="realName"', 6), ('data-validate="leadEmail"', 6),
                             ('data-validate="interest"', 1), ('data-pf-variant=', 3)):
            self.assertContains(response, field, count=count, html=False)
        self.assertContains(response, 'data-commercial-project="m3m-jacob-jewel-crest-noida"', html=False)
        self.assertContains(response, "Jacob &amp; Co Ventures LLC")
        # Logo, locked floor plans that open the popup, drive times in minutes and the private line.
        self.assertContains(response, 'class="lnav__logo"', html=False)
        self.assertContains(response, 'class="jl-plan__card"', count=3, html=False)
        self.assertContains(response, 'data-lm-place="Mall of Noida, Noida"', html=False)
        self.assertContains(response, 'data-jl-pl-slot="evening"', html=False)
        self.assertNotContains(response, "data-jl-pl-day", html=False)
        self.assertContains(response, 'name="visit_date"', html=False)
        self.assertContains(response, 'name="chauffeur"', html=False)
        # Other projects keep the standard page.
        self.assertTemplateUsed(self.client.get("/projects/m3m-the-line-pentsuites"), "projects/detail.html")

    def test_cullinan_uses_its_own_ad_landing_page(self):
        response = self.client.get("/projects/m3m-the-cullinan-residential")
        self.assertTemplateUsed(response, "projects/landing/m3m-the-cullinan-residential.html")
        self.assertTemplateNotUsed(response, "projects/landing/m3m-jacob-co-residences.html")
        # Two-step forms in the hero and final sections, plus the popup's three rotating styles.
        self.assertContains(response, 'name="source" value="landing"', count=5, html=False)
        self.assertContains(response, 'name="unit" value="retail"', count=2, html=False)
        self.assertContains(response, 'data-commercial-project="m3m-the-cullinan-avenue"', count=2, html=False)
        self.assertContains(response, 'class="cl-strip__card"', count=12, html=False)
        self.assertContains(response, "Lavish Buildmart Pvt. Ltd.")
        # Logo, "Cut your own Cullinan", the route map and the private vault.
        self.assertContains(response, 'class="lnav__logo"', html=False)
        self.assertContains(response, "data-cl-cert-form", html=False)
        self.assertContains(response, 'data-lm-place="Amity University, Sector 125, Noida"', html=False)
        self.assertContains(response, 'class="cl-vault__doc"', count=4, html=False)
        self.assertContains(response, "UPRERAPRJ442214")

    def test_jacob_private_line_lead_keeps_the_call_time(self):
        lead = {
            "source": "landing", "name": "Asha Verma", "phone": "9876543210", "email": "asha@gmail.com",
            "interest": "residential", "project": "m3m-jacob-co-residences", "callTime": "evening",
            "message": "Requested: Private line call\nWants: A private site visit\nGood time to talk: Tomorrow, Evening",
        }
        self.assertTrue(self.client.post("/api/enquiries", lead).json()["ok"])
        enquiry = Enquiry.objects.get(source="landing")
        self.assertEqual(enquiry.call_time, "evening")
        self.assertIn("Wants: A private site visit", enquiry.message)
        # Only the known call times are accepted.
        response = self.client.post("/api/enquiries", {**lead, "callTime": "midnight", "phone": "9876543211"})
        self.assertIn("callTime", response.json()["errors"])

    def test_jacob_viewing_pass_lead_keeps_the_visit(self):
        response = self.client.post("/api/enquiries", {
            "source": "landing", "name": "Asha Verma", "phone": "9876543210", "email": "asha@gmail.com",
            "interest": "residential", "project": "m3m-jacob-co-residences", "callTime": "afternoon",
            "visit_date": "2026-11-07", "chauffeur": "on",
            "message": "Requested: Private site visit\nVisit time: Afternoon, 12 – 3 PM",
        })
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get(source="landing")
        self.assertEqual(enquiry.call_time, "afternoon")
        for line in ("Preferred date: 07 Nov 2026", "Chauffeur pickup requested", "Visit time: Afternoon"):
            self.assertIn(line, enquiry.message)

    def test_cullinan_retail_lead_reaches_the_avenue(self):
        response = self.client.post("/api/enquiries", {
            "source": "landing", "name": "Asha Verma", "phone": "9876543210", "email": "asha@gmail.com",
            "interest": "commercial", "project": "m3m-the-cullinan-avenue",
            "message": "Requested: Get retail shop details\nInterested in: Retail shop",
        })
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get(source="landing")
        self.assertEqual(enquiry.project.slug, "m3m-the-cullinan-avenue")
        self.assertIn("Interested in: Retail shop", enquiry.message)

    def test_trump_tower_uses_its_own_ad_landing_page(self):
        response = self.client.get("/projects/m3m-trump-tower-noida")
        self.assertTemplateUsed(response, "projects/landing/m3m-trump-tower-noida.html")
        # Hero, private lift and final forms plus the popup's three rotating styles, each with the residence choice.
        self.assertContains(response, 'name="source" value="landing"', count=6, html=False)
        for field in ('data-validate="choice"', 'data-validate="realName"', 'data-validate="leadEmail"'):
            self.assertContains(response, field, count=6, html=False)
        self.assertContains(response, "not owned, developed or sold by The Trump Organization")
        # Disputed listing figures stay off the page.
        for unverified in ("₹", "crore", "acres", "158"):
            self.assertNotContains(response, unverified)

    def test_trump_tower_lead_records_the_residence(self):
        response = self.client.post("/api/enquiries", {
            "source": "landing", "name": "Asha Verma", "phone": "9876543210", "email": "asha@gmail.com",
            "interest": "residential", "project": "m3m-trump-tower-noida",
            "message": "Requested: Request the private dossier\nInterested in: 5 BHK",
        })
        self.assertTrue(response.json()["ok"])
        enquiry = Enquiry.objects.get(source="landing")
        self.assertEqual(enquiry.project.slug, "m3m-trump-tower-noida")
        self.assertIn("5 BHK", enquiry.message)

    def test_landing_pages_have_their_own_header(self):
        for slug in ("m3m-jacob-co-residences", "m3m-the-cullinan-residential", "m3m-trump-tower-noida"):
            response = self.client.get(f"/projects/{slug}")
            self.assertContains(response, 'class="lnav', html=False)
            self.assertContains(response, 'href="#residences"', html=False)
            self.assertNotContains(response, 'class="site-header"', html=False)
        # Every other page keeps the site menu.
        self.assertContains(self.client.get("/projects/m3m-the-line-pentsuites"), 'class="site-header"', html=False)

    def test_landing_pages_have_their_own_numbers_and_rera_block(self):
        site = SiteSettings.load(m3m())
        for slug, whatsapp in (("m3m-jacob-co-residences", "917399673996"),
                               ("m3m-the-cullinan-residential", "917399473994"),
                               ("m3m-trump-tower-noida", "917399473994")):
            response = self.client.get(f"/projects/{slug}")
            self.assertContains(response, 'href="tel:+917399473994"', html=False)
            self.assertContains(response, f"https://wa.me/{whatsapp}", html=False)
            self.assertContains(response, 'class="lnav__whatsapp"', html=False)
            self.assertNotContains(response, f"tel:{site.phone_dial}", html=False)
            self.assertNotContains(response, site.phone_display)
            self.assertNotContains(response, "Toll-free")
            # The RERA number, the regulator's website and the QR code, on the banner.
            self.assertContains(response, 'class="lrera lrera--', html=False)
            self.assertContains(response, Project.objects.get(slug=slug).rera)
            self.assertContains(response, 'href="https://www.up-rera.in/projects"', html=False)
            self.assertContains(response, "rera-qr", html=False)
        self.assertContains(self.client.get("/projects/m3m-the-cullinan-residential"), "UPRERAAGT10202")
        # The rest of the site keeps its own numbers.
        response = self.client.get("/projects/m3m-the-line-pentsuites")
        self.assertContains(response, f"tel:{site.phone_dial}", html=False)
        self.assertContains(response, "Toll-free")

    def test_landing_routes_start_at_the_project(self):
        for slug, origin in (("m3m-jacob-co-residences", "M3M Jacob &amp; Co. Residences, Sector 97, Noida"),
                             ("m3m-the-cullinan-residential", "M3M The Cullinan, Sector 94, Noida"),
                             ("m3m-trump-tower-noida", "Trump Towers Noida, Sector 94, Noida")):
            self.assertContains(self.client.get(f"/projects/{slug}"), f'data-origin="{origin}"', html=False)

    def test_landing_popups_rotate_the_three_form_styles(self):
        # Each page's popup starts with the next page's form style: Jacob → b, Cullinan → c, Trump → a.
        for slug, start, theme in (("m3m-jacob-co-residences", "b", "jl"),
                                   ("m3m-the-cullinan-residential", "c", "cl"),
                                   ("m3m-trump-tower-noida", "a", "tt")):
            response = self.client.get(f"/projects/{slug}")
            self.assertContains(response, f'class="pf pf--{theme}" data-pf data-pf-start="{start}"', html=False)
            self.assertContains(response, "js/landing-forms.js", html=False)
            self.assertContains(response, "js/landing-fx.js", html=False)

    def test_homepage_teases_billionaire_block(self):
        response = self.client.get("/")
        self.assertContains(response, 'class="bbt"', html=False)
        self.assertContains(response, "Something extraordinary is rising.")
        self.assertContains(response, 'href="/billionaire-block"', html=False)
        self.assertContains(response, "/billionaire-block#private-viewing", html=False)
        # The light projects section separates the dark banner from the dark teaser.
        html = response.content.decode()
        self.assertLess(html.index('class="phase-one-hero"'), html.index('id="projects"'))
        self.assertLess(html.index('id="projects"'), html.index('class="bbt"'))

    def test_billionaire_block_is_editable(self):
        page = BillionaireBlockPage.load(m3m())
        page.tagline = "A new horizon."
        page.save()
        self.assertContains(self.client.get("/billionaire-block"), "A new horizon.")

    def test_landing_pages_are_edited_in_the_admin(self):
        self.assertEqual(
            set(LandingPage.objects.values_list("slug", flat=True)),
            {"m3m-jacob-co-residences", "m3m-the-cullinan-residential", "m3m-trump-tower-noida", "billionaire-block", "website-texts"},
        )
        for page in LandingPage.objects.all():
            self.assertTrue(page.texts.exists(), page)
            self.assertTrue(page.items.exists(), page)
        trump = LandingPage.objects.get(slug="m3m-trump-tower-noida")
        LandingText.objects.filter(page=trump, key="res_title").update(value="Homes with a *new name.*")
        trump.items.filter(list_key="faq").update(is_published=False)
        trump.items.create(list_key="faq", title="Is parking included?", text="Yes, RERA {rera}.")
        response = self.client.get("/projects/m3m-trump-tower-noida")
        self.assertContains(response, "Homes with a <em>new name.</em>", html=False)
        self.assertContains(response, "Is parking included?")
        self.assertContains(response, f"Yes, RERA {Project.objects.get(slug='m3m-trump-tower-noida').rera}.")
        self.assertNotContains(response, "Which residences are available?")

    def test_project_without_landing_content_uses_the_standard_page(self):
        LandingPage.objects.filter(slug="m3m-trump-tower-noida").delete()
        response = self.client.get("/projects/m3m-trump-tower-noida")
        self.assertTemplateUsed(response, "projects/detail.html")
        self.assertTemplateNotUsed(response, "projects/landing/m3m-trump-tower-noida.html")

    def test_large_upload_is_downsized(self):
        admin = User.objects.create_superuser("admin", "a@example.com", "pass")
        self.client.force_login(admin)
        buffer = BytesIO()
        Image.new("RGB", (4000, 2000), "navy").save(buffer, "JPEG")
        upload = SimpleUploadedFile("huge.jpg", buffer.getvalue(), content_type="image/jpeg")
        response = self.client.post("/admin/core/herobanner/add/", {"image": upload, "order": 1, "is_active": "on"})
        self.assertEqual(response.status_code, 302)
        banner = HeroBanner.objects.order_by("-pk").first()
        self.assertEqual(banner.image.width, 2560)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class MenuPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", verbosity=0)

    def setUp(self):
        cache.clear()

    def test_every_menu_page_renders_with_its_banner(self):
        for page in InnerPage.objects.all():
            response = self.client.get(page.get_absolute_url())
            self.assertEqual(response.status_code, 200, page.key)
            self.assertContains(response, page.title)
            self.assertContains(response, 'class="inner-hero"')
            self.assertContains(response, 'aria-current="page"')
            self.assertContains(response, page.form_title)
            self.assertContains(response, f'name="source" value="{page.form_source}"')

    def test_banner_form_hides_without_a_title(self):
        InnerPage.objects.filter(key="media").update(form_title="")
        self.assertNotContains(self.client.get("/media-centre"), "inner-hero__aside")

    def test_projects_page_groups_collections(self):
        response = self.client.get("/projects")
        for name in ("Now Presenting", "On the Horizon", "Delivered Landmarks"):
            self.assertContains(response, name)
        self.assertContains(response, 'class="project-card"', count=9)

    def test_project_status_moves_it_between_collections(self):
        Project.objects.update(status=Project.Status.CURRENT)
        response = self.client.get("/projects")
        self.assertContains(response, "New addresses for this collection will be announced soon.", count=2)

    def test_homepage_featured_projects(self):
        Project.objects.update(is_featured=False)
        Project.objects.filter(slug="smartworld-noida-commercial").update(is_featured=True)
        featured = Project.objects.for_homepage()
        self.assertEqual(featured[0].slug, "smartworld-noida-commercial")
        self.assertEqual(len(featured), 3)

    def test_insight_article(self):
        insight = Insight.objects.get(slug="reading-a-rera-registration-a-buyers-checklist")
        response = self.client.get(insight.get_absolute_url())
        self.assertContains(response, "<h2>Understand carpet area</h2>", html=True)
        self.assertContains(response, "More <em>insights.</em>", html=True)

    def test_media_page_lists_gallery_and_press(self):
        response = self.client.get("/media-centre")
        self.assertContains(response, 'class="masonry__item"', count=13)
        self.assertContains(response, "Moneycontrol")
        self.assertNotContains(response, 'id="films"')
        Video.objects.create(builder=m3m(), title="Walkthrough", youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertContains(self.client.get("/media-centre"), "dQw4w9WgXcQ")

    def test_contact_page(self):
        response = self.client.get("/contact")
        self.assertContains(response, 'value="contact"')
        self.assertContains(response, "Frequently")

    def test_video_id_parsing(self):
        for url in ["https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=3",
                    "https://www.youtube.com/shorts/dQw4w9WgXcQ"]:
            self.assertEqual(Video(youtube_url=url).youtube_id, "dQw4w9WgXcQ")


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PressTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", verbosity=0)

    def test_news_cards_show_publication_logos(self):
        from content.models import Publication

        response = self.client.get("/")
        for publication in Publication.objects.filter(items__is_published=True).distinct():
            self.assertTrue(publication.logo, publication.name)
            self.assertContains(response, publication.logo.url)
        self.assertContains(response, "As featured in")
        self.assertContains(response, 'class="press-card press-card--publication"', count=3)
        self.assertContains(self.client.get("/media-centre"), "Read on Outlook Luxe")
