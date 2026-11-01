"""
Load the first builder's (M3M's) starting content: its projects, press, gallery, articles and pages.

    python manage.py seed_content            # add anything that is missing
    python manage.py seed_content --update   # also overwrite edited rows

Safe to run more than once: rows are matched by slug / title within the builder. A new builder does not use this
command: adding it in the admin (or `manage.py create_builder`) gives it its own empty starting pages.
"""

import datetime
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from content.models import Insight, JourneyPrinciple, JourneyStat, MediaImage, Milestone, PressItem, Publication
from core import seed_pages
from core.branding import apply_first_builder_branding
from core.models import FAQ, HeroBanner, HomePage, InnerPage, Page, SiteSettings
from projects import landing
from projects.models import BillionaireBlockPage, BillionaireItem, BillionaireNews, BillionaireResidence, Project
from tenants.migration_helpers import FIRST_BUILDER_SLUG
from tenants.models import Builder

SEED_IMAGES = Path(settings.BASE_DIR) / "seed" / "images"

PROJECTS = [
    {
        "slug": "m3m-jacob-co-residences",
        "name": "M3M Jacob & Co. Residences",
        "category": "M3M Jacob & Co.",
        "interests": ["residential"],
        "offering": "3, 4 & 5 BHK Apartments",
        "location": "Sector 97, Noida Expressway",
        "rera": "UPRERAPRJ690055/10/2025",
        "image": "projects_main/m3m_jacob_co.jpg",
        "summary": "A collection of 3, 4 and 5 BHK residences at Sector 97, Noida Expressway.",
    },
    {
        "slug": "m3m-jacob-jewel-crest-noida",
        "name": "M3M Jewel Crest Avenue",
        "category": "M3M Jacob & Co.",
        "interests": ["commercial"],
        "offering": "High-Street Retail, Fine Dining & Cafés",
        "location": "Sector 97, Noida Expressway",
        "rera": "UPRERAPRJ690055/10/2025",
        "image": "projects_main/m3m_jacob_jewel.jpg",
        "summary": "High-street retail, fine dining and cafés, integrated with the Jacob & Co. residences on Noida Expressway.",
    },
    {
        "slug": "m3m-the-line-retail-shops",
        "name": "M3M The Line Retail Shops",
        "category": "M3M The Line",
        "interests": ["residential", "commercial"],
        "offering": "Studio Apartments, Retail Shops & Food Court",
        "location": "Sector 72, Central Noida",
        "rera": "UPRERAPRJ246070",
        "image": "projects_main/m3m_line_Retail_shops.jpg",
        "summary": "Studio apartments, retail shops and a food court at Sector 72, Central Noida.",
    },
    {
        "slug": "m3m-the-line-pentsuites",
        "name": "M3M The Line Pentsuites",
        "category": "M3M The Line",
        "interests": ["residential"],
        "offering": "1 BHK Serviced Apartment",
        "location": "Sector 72, Central Noida",
        "rera": "UPRERAPRJ246070",
        "image": "projects_main/m3m_line_pentsuit.jpg",
        "summary": "1 BHK serviced apartments at Sector 72, Central Noida.",
    },
    {
        "slug": "m3m-the-cullinan-residential",
        "name": "M3M The Cullinan Residential",
        "category": "M3M The Cullinan",
        "interests": ["residential"],
        "offering": "3, 4 & 5 BHK Apartments",
        "location": "Sector 94, Noida Expressway",
        "rera": "UPRERAPRJ442214",
        "image": "projects_main/m3m_culinen_m.webp",
        "summary": "A range of 3, 4 and 5 BHK apartments at Sector 94, Noida Expressway.",
    },
    {
        "slug": "m3m-the-cullinan-avenue",
        "name": "M3M The Cullinan Avenue",
        "category": "M3M The Cullinan",
        "interests": ["commercial"],
        "offering": "Commercial Retail Shops",
        "location": "Sector 94, Noida Expressway",
        "rera": "UPRERAPRJ442214",
        "image": "projects_main/m3m_culinen_avenue.webp",
        "summary": "Commercial retail shops at Sector 94, Noida Expressway.",
    },
    {
        "slug": "smartworld-noida-residential",
        "name": "Smartworld Noida Residential",
        "category": "Smartworld Noida",
        "interests": ["residential"],
        "offering": "3 & 4 BHK Residences",
        "location": "Sector 98, Noida Expressway",
        "rera": "UPRERAPRJ300532/12/2025",
        "image": "projects_main/m3m_smart_world_noida_residence.webp",
        "summary": "3 and 4 BHK branded residences at Sector 98, Noida Expressway.",
    },
    {
        "slug": "smartworld-noida-commercial",
        "name": "Smartworld Noida Commercial",
        "category": "Smartworld Noida",
        "interests": ["residential", "commercial"],
        "offering": "1 & 2 BHK Serviced Suites, Retail, Cafés & Dining",
        "location": "Sector 98, Noida Expressway",
        "rera": "UPRERAPRJ300532/12/2025",
        "image": "projects_main/m3m_smar_world_noida_commercial.webp",
        "summary": "Serviced suites, retail, cafés and dining at Sector 98, Noida Expressway.",
    },
    {
        "slug": "m3m-trump-tower-noida",
        "name": "M3M Trump Tower Noida",
        "category": "M3M Trump Tower",
        "interests": ["residential"],
        "offering": "4 & 5 BHK Apartments",
        "location": "Sector 94, Noida Expressway",
        "rera": "UPRERAPRJ794824/10/2025",
        "image": "projects_main/m3m_trump_tower.jpg",
        "summary": "A collection of 4 and 5 BHK apartments at Sector 94, Noida Expressway.",
    },
]

PRINCIPLES = [
    (
        "Trust, built into every step",
        "Clear communication and considered guidance help people make confident decisions at every stage of their property journey.",
    ),
    (
        "Design that earns its place",
        "Architecture, amenities and everyday functionality are brought together to make each address feel purposeful and enduring.",
    ),
    (
        "A long view of growth",
        "From new neighbourhoods in Noida to established destinations across the region, each development contributes to a wider urban story.",
    ),
    (
        "Places for people",
        "Homes and destinations matter most when they support the routines, connections and ambitions of the people who use them.",
    ),
]

STATS = [("2010", "Year of founding"), ("66", "Projects in the portfolio"), ("43", "Projects delivered")]

# Verified coverage (headline, date and link checked against each publisher's page).
PUBLICATIONS = [
    ("Moneycontrol", "press-logos/moneycontrol.png", "https://www.moneycontrol.com"),
    ("Business Standard", "press-logos/business-standard.png", "https://www.business-standard.com"),
    ("ET Realty", "press-logos/et-realty.png", "https://realty.economictimes.indiatimes.com"),
    ("Outlook Luxe", "press-logos/outlook-luxe.png", "https://luxe.outlookindia.com"),
]

PRESS = [
    {
        "title": "M3M bags Rs 1,839 crore mega Noida land deal, pips DLF",
        "publication": "Moneycontrol",
        "published_on": datetime.date(2026, 9, 8),
        "summary": "Moneycontrol reports that M3M India emerged as the highest bidder for a 12.5-acre land parcel in Noida’s Sector 108, at ₹1,839 crore, more than twice the Noida Authority’s initial price.",
        "article_url": "https://www.moneycontrol.com/news/business/real-estate/dlf-loses-rs-1-839-crore-mega-noida-land-deal-to-m3m-14025528.html",
    },
    {
        "title": "M3M India to invest ₹600 crore to build commercial project in Gurugram",
        "publication": "Business Standard",
        "published_on": datetime.date(2026, 7, 30),
        "summary": "Business Standard covers the launch of M3M Capital Financial Center on Dwarka Expressway, Gurugram: a ₹600 crore commercial project expected to be completed by 2029.",
        "article_url": "https://www.business-standard.com/industry/news/m3m-india-to-invest-600-crore-to-build-commercial-project-in-gurugram-126073000832_1.html",
    },
    {
        "title": "M3M India deploys ₹14,500 crore to fund construction of over 45 million sq ft",
        "publication": "ET Realty",
        "published_on": datetime.date(2026, 4, 1),
        "summary": "ET Realty reports on M3M India’s ₹14,500 crore programme to accelerate construction across its 45 million sq ft portfolio, highlighting the company’s zero-debt strategy.",
        "article_url": "https://realty.economictimes.indiatimes.com/news/industry/m3m-india-unveils-14500-crore-construction-acceleration-programme-for-45-million-sq-ft-portfolio/129946559",
    },
    {
        "title": "M3M Group to invest ₹10,000 crore in construction, land acquisition in FY27",
        "publication": "Business Standard",
        "published_on": datetime.date(2026, 7, 1),
        "summary": "Business Standard reports that the M3M Group plans to invest ₹7,200 crore in construction and ₹2,500 crore in land acquisition in FY27 as it expands its project pipeline and branded housing portfolio.",
        "article_url": "https://www.business-standard.com/companies/news/m3m-group-to-invest-10-000-crore-in-construction-land-acquisition-in-fy27-126070101408_1.html",
    },
    {
        "title": "M3M India, Smartworld Developers tie up with ELIE SAAB for ₹3,500-crore housing projects in NCR",
        "publication": "ET Realty",
        "published_on": datetime.date(2026, 1, 14),
        "summary": "ET Realty reports that M3M India and Smartworld Developers have partnered with ELIE SAAB on two luxury residential projects in Delhi-NCR: about 950 apartments with a total investment of ₹3,500 crore, set for completion by 2030.",
        "article_url": "https://realty.economictimes.indiatimes.com/news/industry/m3m-india-smartworld-developers-tie-up-with-elie-saab-for-3500-crore-housing-projects-in-ncr/126536979",
    },
    {
        "title": "M3M India to invest ₹7,200 cr to build 150-acre township in Gurugram",
        "publication": "Business Standard",
        "published_on": datetime.date(2025, 11, 5),
        "summary": "Business Standard reports M3M India’s plan to invest ₹7,200 crore in a 150-acre integrated township in Gurugram as part of its expansion.",
        "article_url": "https://www.business-standard.com/companies/news/m3m-india-to-invest-7-200-cr-to-build-150-acre-township-in-gurugram-125110500645_1.html",
    },
    {
        "title": "M3M India launches Jacob & Co. Residences in Noida, unveiling India’s first ultra-luxury branded homes under the iconic maison",
        "publication": "Outlook Luxe",
        "published_on": datetime.date(2025, 10, 16),
        "summary": "Outlook Luxe on the launch of Jacob & Co. Residences in Noida, the first homes in India under the Jacob & Co. brand.",
        "article_url": "https://luxe.outlookindia.com/art-design/home/m3m-india-launches-jacob-co-residences-in-noida-unveiling-indias-first-ultra-luxury-branded-homes-under-the-iconic-maison",
    },
]

MEDIA = [
    ("media/m1.jpeg", "A welcoming sense of arrival"),
    ("media/m2.jpeg", "Spaces made for gathering"),
    ("media/m3.jpeg", "Wellness, thoughtfully considered"),
    ("media/m4.jpeg", "An architectural first impression"),
    ("media/m5.jpeg", "A quieter moment by the water"),
    ("media/m6.jpeg", "Room to move and reset"),
    ("media/m7.jpeg", "A pool framed by the city"),
    ("media/m8.jpeg", "Evenings with a point of view"),
    ("media/m9.jpeg", "Landscaped spaces to unwind"),
    ("media/m10.jpeg", "A little more room to play"),
    ("media/m11.jpeg", "A landmark on the skyline"),
    ("media/m12.jpeg", "An illuminated expression of design"),
    ("media/m13.jpeg", "A new perspective on the city"),
]

PAGES = [
    ("Privacy", "privacy"),
    ("Disclaimer", "disclaimer"),
    ("Compliance", "compliance"),
]


class Command(BaseCommand):
    help = "Load the original website content (projects, press, gallery…) into the database."

    def add_arguments(self, parser):
        parser.add_argument("--update", action="store_true", help="Overwrite rows that already exist.")
        parser.add_argument("--builder", default=FIRST_BUILDER_SLUG, help="Slug of the builder to load it into.")

    @transaction.atomic
    def handle(self, *args, update=False, builder=FIRST_BUILDER_SLUG, **options):
        self.update = update
        self.builder = Builder.objects.get(slug=builder)
        site = SiteSettings.objects.filter(builder=self.builder).first() or SiteSettings.create_for(self.builder)
        apply_first_builder_branding(site, self.builder.slug)
        site.save()
        HomePage.objects.filter(builder=self.builder).first() or HomePage.create_for(self.builder)

        if not HeroBanner.objects.for_builder(self.builder).exists():
            banner = HeroBanner(builder=self.builder, alt_text="Towers rising above the clouds at sunset", order=0)
            self._attach(banner, "image", "home_banners/towers-above-clouds.jpg")
            self._attach(banner, "video", "billionaire_block/hero.mp4")
            banner.save()

        for order, data in enumerate(PROJECTS):
            data = dict(data)
            interests = data.pop("interests")
            image = data.pop("image")
            data.update(
                order=order,
                is_residential="residential" in interests,
                is_commercial="commercial" in interests,
                status=seed_pages.PROJECT_STATUS[data["slug"]],
                is_featured=data["slug"] in seed_pages.FEATURED_PROJECTS,
            )
            self._upsert(Project, {"slug": data.pop("slug")}, data, image=image)

        for order, (title, description) in enumerate(PRINCIPLES):
            self._upsert(JourneyPrinciple, {"title": title}, {"description": description, "order": order})
        for order, (value, label) in enumerate(STATS):
            self._upsert(JourneyStat, {"label": label}, {"value": value, "order": order})
        publications = {}
        for name, logo, website in PUBLICATIONS:
            publication, _ = Publication.objects.get_or_create(
                builder=self.builder, name=name, defaults={"website": website}
            )
            if not publication.logo or self.update:
                publication.website = website
                self._attach(publication, "logo", logo)
                publication.save()
            publications[name] = publication
        for order, data in enumerate(PRESS):
            data = dict(data)
            data["publication"] = publications[data["publication"]]
            self._upsert(PressItem, {"title": data.pop("title")}, {**data, "order": order})
        for order, (image, caption) in enumerate(MEDIA):
            category = seed_pages.MEDIA_CATEGORIES[caption]
            self._upsert(MediaImage, {"caption": caption}, {"order": order, "category": category}, image=image)
        for order, data in enumerate(seed_pages.INSIGHT_ARTICLES):
            data = dict(data)
            image = data.pop("image")
            self._upsert(Insight, {"title": data.pop("title")}, {**data, "order": order}, image=image)
        for order, (marker, title, description) in enumerate(seed_pages.MILESTONES):
            self._upsert(Milestone, {"title": title}, {"marker": marker, "description": description, "order": order})
        for order, (question, answer) in enumerate(seed_pages.FAQS):
            self._upsert(FAQ, {"question": question}, {"answer": answer, "order": order})
        for data in seed_pages.INNER_PAGES:
            data = dict(data)
            banner = data.pop("banner")
            page = self._upsert(InnerPage, {"key": data.pop("key")}, data)
            if not page.banner:
                self._attach(page, "banner", banner)
                page.save()

        self._seed_billionaire_block()

        disclaimer = site.footer_disclaimer
        for title, slug in PAGES:
            body = disclaimer if slug == "disclaimer" else f"{title} information for M3M India will be published here."
            Page.objects.get_or_create(
                builder=self.builder, slug=slug, defaults={"title": title, "body": body, "is_published": slug == "disclaimer"}
            )
        # The landing pages created by migrations become their projects' main pages.
        landing.link_projects(self.builder)

        if options["verbosity"]:
            self.stdout.write(self.style.SUCCESS("Website content is loaded."))

    def _seed_billionaire_block(self):
        page = BillionaireBlockPage.objects.filter(builder=self.builder).first() or BillionaireBlockPage.create_for(
            self.builder
        )
        if not page.rera_number:
            page.rera_number = seed_pages.BILLIONAIRE_RERA
        for field, path in seed_pages.BILLIONAIRE_BLOCK_FILES.items():
            if (not getattr(page, field) or self.update) and (SEED_IMAGES / path).exists():
                self._attach(page, field, path)
        page.save()
        for order, (name, tagline, size, configuration, features, image, alt) in enumerate(
            seed_pages.BILLIONAIRE_RESIDENCES
        ):
            values = {
                "tagline": tagline,
                "size": size,
                "configuration": configuration,
                "features": features,
                "image_alt": alt,
                "order": order,
            }
            self._upsert(BillionaireResidence, {"page": page, "name": name}, values, image=image)
        for order, (tag, title, publication, date, summary, body, points, url, paid) in enumerate(
            seed_pages.BILLIONAIRE_NEWS
        ):
            values = {
                "tag": tag,
                "publication": publication,
                "published_on": date,
                "summary": summary,
                "body": body,
                "key_points": points,
                "url": url,
                "is_press_release": paid,
                "order": order,
            }
            self._upsert(BillionaireNews, {"page": page, "title": title}, values)
        for order, (section, title, value, text, image, alt) in enumerate(seed_pages.BILLIONAIRE_ITEMS):
            values = {"value": value, "text": text, "image_alt": alt, "order": order}
            self._upsert(BillionaireItem, {"section": section, "title": title}, values, image=image or None)

    def _upsert(self, model, lookup, values, image=None):
        if any(field.name == "builder" for field in model._meta.fields):
            lookup = {"builder": self.builder, **lookup}
        obj = model.objects.filter(**lookup).first()
        created = obj is None
        if created:
            obj = model(**lookup)
        elif not self.update:
            return obj
        for field, value in values.items():
            setattr(obj, field, value)
        if image and (created or self.update):
            self._attach(obj, "image", image)
        obj.save()
        return obj

    def _attach(self, obj, field, relative_path):
        source = SEED_IMAGES / relative_path
        with source.open("rb") as handle:
            getattr(obj, field).save(source.name, File(handle), save=False)
