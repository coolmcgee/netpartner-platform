from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# Tiers from lowest to highest (used to compare "is this creator high enough?")
TIER_ORDER = ["Starter", "Emerging", "Rising", "Established", "Premier", "Signature"]

# Physical-product gate. Placeholder numbers: set properly after market research.
GATE_MIN_RATING = 60
GATE_MIN_COMPLETED = 3
GATE_MIN_ENGAGEMENT = Decimal("2.0")   # % engagement rate
GATE_MIN_NZ_PCT = 50                   # % of followers in NZ

# Money. Placeholders: set properly after market research.
PLATFORM_FEE = Decimal("0.15")   # added on top for brands; creators keep 100%
PAYOUT_MIN = Decimal("20")       # creators are paid once earnings are over this
PAYOUT_WAIT_DAYS = 7             # view check: wait this long after posting before paying


class Brand(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    website = models.URLField(blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="brand_profile",
    )

    def __str__(self):
        return self.name


class Campaign(models.Model):
    class Type(models.TextChoices):
        VIEWS = "views", "View campaign (paid per 1,000 views)"
        CLIPPING = "clipping", "Clipping"
        AFFILIATE = "affiliate", "Affiliate / referral code"
        BRAND_CONTENT = "brand_content", "Content for the brand's own page"
        DIGITAL_UGC = "digital_ugc", "Digital UGC (apps, websites, services)"
        GIFTED = "gifted", "Gifted product"
        UGC = "ugc", "UGC with a physical product"
        PAID_POST = "paid_post", "Small paid post"
        SPONSORED = "sponsored", "Paid sponsored post"

    # Lowest tier allowed to apply for each type
    MIN_TIER = {
        "views": "Starter",
        "clipping": "Starter",
        "affiliate": "Starter",
        "brand_content": "Starter",
        "digital_ugc": "Starter",
        "gifted": "Emerging",
        "ugc": "Starter",        # any tier, but must pass the product gate (early unlock by Rating)
        "paid_post": "Rising",
        "sponsored": "Established",
    }

    # Types where the brand ships something, so the product gate applies
    PRODUCT_TYPES = {"gifted", "ugc"}

    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="campaigns")
    name = models.CharField(max_length=100)
    campaign_type = models.CharField(max_length=20, choices=Type.choices, default=Type.VIEWS)
    brief = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    pay_per_creator = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="What each accepted creator gets paid (NZD). 0 = gifted only.",
    )
    post_by = models.DateField()
    approved = models.BooleanField(
        default=False, help_text="Tick after your safety check. Creators only see approved campaigns.",
    )

    @property
    def platform_fee(self):
        return (self.budget * PLATFORM_FEE).quantize(Decimal("0.01"))

    @property
    def total_to_pay(self):
        return self.budget + self.platform_fee

    @property
    def spots(self):
        """How many creators the budget covers (None if unpaid/gifted)."""
        if not self.pay_per_creator:
            return None
        return int(self.budget // self.pay_per_creator)

    @property
    def min_tier(self):
        return self.MIN_TIER.get(self.campaign_type, "Starter")

    @property
    def needs_product(self):
        return self.campaign_type in self.PRODUCT_TYPES

    def __str__(self):
        return self.name


class Creator(models.Model):
    handle = models.CharField(max_length=60)          # e.g. aria.creates
    niche = models.CharField(max_length=50)
    followers = models.PositiveIntegerField(default=0)
    rating = models.PositiveIntegerField(default=50)  # everyone starts at 50
    engagement_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Engagement % from their insights screenshots",
    )
    nz_audience_pct = models.PositiveSmallIntegerField(
        default=0, help_text="% of followers in NZ, from insights",
    )
    insights_checked = models.BooleanField(
        default=False, help_text="Tick once you've checked their insights screenshots",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="creator",
    )

    @property
    def tier(self):
        f = self.followers
        if f >= 100_000: return "Signature"
        if f >= 50_000:  return "Premier"
        if f >= 10_000:  return "Established"
        if f >= 5_000:   return "Rising"
        if f >= 1_000:   return "Emerging"
        return "Starter"

    @property
    def is_paused(self):
        """3 missed posts in 90 days = paused for 2 weeks after the latest miss."""
        since = timezone.now() - timedelta(days=90)
        misses = self.rating_events.filter(reason="Missed post", created_at__gte=since)
        if misses.count() < 3:
            return False
        return timezone.now() < misses.first().created_at + timedelta(days=14)

    @property
    def completed_count(self):
        return self.applications.filter(status__in=["verified", "paid"]).count()

    def product_gate_missing(self):
        """List of what this creator still needs before brands can send them products."""
        missing = []
        if self.rating < GATE_MIN_RATING:
            missing.append(f"Rating {GATE_MIN_RATING}+ (you're at {self.rating})")
        done = self.completed_count
        if done < GATE_MIN_COMPLETED:
            missing.append(f"{GATE_MIN_COMPLETED} completed campaigns (you've done {done})")
        if not self.insights_checked:
            missing.append("verified insights")
        else:
            if self.engagement_rate < GATE_MIN_ENGAGEMENT:
                missing.append(f"{GATE_MIN_ENGAGEMENT}%+ engagement")
            if self.nz_audience_pct < GATE_MIN_NZ_PCT:
                missing.append(f"{GATE_MIN_NZ_PCT}%+ NZ audience")
        return missing

    @property
    def passes_product_gate(self):
        return not self.product_gate_missing()

    def eligibility(self, campaign):
        """Can this creator apply? Returns (True, "") or (False, reason)."""
        if TIER_ORDER.index(self.tier) < TIER_ORDER.index(campaign.min_tier):
            return False, f"Unlocks at {campaign.min_tier} tier"
        if campaign.needs_product:
            missing = self.product_gate_missing()
            if missing:
                return False, "Needs " + ", ".join(missing)
        return True, ""

    def __str__(self):
        return self.handle


class Application(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        DRAFTING = "drafting", "Drafting"
        POSTED = "posted", "Posted"
        VERIFIED = "verified", "Verified"
        PAID = "paid", "Paid"
        MISSED = "missed", "Missed"

    creator = models.ForeignKey(Creator, on_delete=models.CASCADE, related_name="applications")
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="applications")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    applied_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True)   # set when moved to "posted"
    amount = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="What this creator gets for this campaign (set on accept)",
    )

    @property
    def payout_ready(self):
        """Verified, and the 7-day view check has passed."""
        if self.status != self.Status.VERIFIED or self.posted_at is None:
            return False
        return self.posted_at <= timezone.now() - timedelta(days=PAYOUT_WAIT_DAYS)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["creator", "campaign"], name="one_application_per_campaign"
            ),
        ]

    def __str__(self):
        return f"{self.creator} → {self.campaign} ({self.status})"


class RatingEvent(models.Model):
    creator = models.ForeignKey(Creator, on_delete=models.CASCADE, related_name="rating_events")
    application = models.ForeignKey(
        Application, null=True, blank=True, on_delete=models.SET_NULL
    )
    change = models.SmallIntegerField()
    reason = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.creator} {self.change:+d} ({self.reason})"


class Review(models.Model):
    """A brand's review of a creator after the post is verified. Feeds the Rating."""
    STARS = [(5, "5 ★ Excellent"), (4, "4 ★ Good"), (3, "3 ★ OK"), (2, "2 ★ Poor"), (1, "1 ★ Bad")]

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="review")
    stars = models.PositiveSmallIntegerField(choices=STARS)
    comment = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.application.creator}: {self.stars}★"