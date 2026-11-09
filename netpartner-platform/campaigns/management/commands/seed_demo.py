import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from campaigns.models import Application, Brand, Campaign, Creator, RatingEvent, Review

PASSWORD = "demo-pass-123"

# handle, niche, followers, rating, engagement %, NZ %
CREATORS = [
    ("aria.eats.chch", "Food & cafés", 2400, 72, "5.8", 81),
    ("tama.trains", "Fitness", 8700, 66, "4.1", 74),
    ("mia.wears.nz", "Fashion", 14200, 81, "3.6", 69),
    ("kiwi.glow", "Beauty & skincare", 3100, 63, "6.2", 88),
    ("jordan.outdoors", "Outdoors", 950, 55, "7.4", 92),
    ("lena.studies", "Student life", 600, 50, "8.1", 95),
    ("noah.cooks", "Food & cafés", 5600, 58, "3.9", 77),
    ("sophie.lifts", "Fitness", 1800, 44, "2.7", 61),
]

# handle -> status on the main demo campaign
STAGES = {
    "aria.eats.chch": "paid",
    "tama.trains": "verified",
    "mia.wears.nz": "posted",
    "kiwi.glow": "drafting",
    "noah.cooks": "accepted",
    "sophie.lifts": "missed",
    "jordan.outdoors": "pending",
    "lena.studies": "pending",
}


class Command(BaseCommand):
    help = "Fill the site with demo data for brand sales calls. Safe to run again."

    def handle(self, *args, **options):
        # Wipe old demo data (only users starting with demo_)
        User.objects.filter(username__startswith="demo_").delete()
        Brand.objects.filter(name__endswith="(demo)").delete()
        Creator.objects.filter(handle__in=[c[0] for c in CREATORS]).delete()

        now = timezone.now()
        today = timezone.localdate()

        brand_user = User.objects.create_user("demo_brand", "demo@kowhai.nz", PASSWORD)
        brand = Brand.objects.create(
            name="Kōwhai Skincare (demo)", email="demo@kowhai.nz",
            website="https://example.com", user=brand_user,
        )

        main = Campaign.objects.create(
            brand=brand, name="Summer Glow UGC", campaign_type="brand_content",
            brief="Film a 20–30s video using our SPF moisturiser outdoors. Natural light, "
                  "show the texture, mention it's made in NZ. Usage rights: 6 months. Tag #ad.",
            budget=Decimal("1200"), pay_per_creator=Decimal("150"),
            post_by=today + datetime.timedelta(days=4), approved=True,
        )
        Campaign.objects.create(
            brand=brand, name="Café Week Views", campaign_type="views",
            brief="Post a Reel at your favourite Christchurch café featuring our hand cream. "
                  "Paid per 1,000 views, capped per creator. Tag #ad.",
            budget=Decimal("600"), pay_per_creator=Decimal("40"),
            post_by=today + datetime.timedelta(days=12), approved=True,
        )
        Campaign.objects.create(
            brand=brand, name="Gifted: Winter Repair Kit", campaign_type="gifted",
            brief="We send you our Winter Repair Kit. Post one honest Story and one Reel. Tag #ad.",
            budget=Decimal("0"), pay_per_creator=Decimal("0"),
            post_by=today + datetime.timedelta(days=20), approved=False,
        )

        creators = {}
        for handle, niche, followers, rating, eng, nz in CREATORS:
            u = User.objects.create_user(f"demo_{handle.split('.')[0]}", f"{handle}@example.com", PASSWORD)
            creators[handle] = Creator.objects.create(
                user=u, handle=handle, niche=niche, followers=followers, rating=rating,
                engagement_rate=Decimal(eng), nz_audience_pct=nz, insights_checked=True,
            )

        for handle, status in STAGES.items():
            c = creators[handle]
            paid_stage = status in ("accepted", "drafting", "posted", "verified", "paid")
            app = Application.objects.create(
                creator=c, campaign=main, status=status,
                amount=main.pay_per_creator if paid_stage else 0,
            )
            if status in ("posted", "verified", "paid"):
                days_ago = {"posted": 1, "verified": 3, "paid": 9}[status]
                app.posted_at = now - datetime.timedelta(days=days_ago)
                app.save(update_fields=["posted_at"])
            if status in ("verified", "paid"):
                RatingEvent.objects.create(creator=c, application=app, change=5, reason="On-time post")
            if status == "paid":
                Review.objects.create(application=app, stars=5, comment="Amazing content, super easy to work with.")
                RatingEvent.objects.create(creator=c, application=app, change=3, reason="Brand review (5★)")
            if status == "missed":
                RatingEvent.objects.create(creator=c, application=app, change=-10, reason="Missed post")

        self.stdout.write(self.style.SUCCESS(
            "Demo data ready.\n"
            f"  Brand login:   demo_brand / {PASSWORD}\n"
            f"  Creator login: demo_aria / {PASSWORD}  (also demo_tama, demo_mia, demo_kiwi ...)\n"
            "  Main campaign: Summer Glow UGC (open its tracker)"
        ))