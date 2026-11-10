from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# Tiers from lowest to highest (used to compare "is this creator high enough?")
TIER_ORDER = ["Starter", "Emerging", "Rising", "Established", "Premier", "Signature"]


def tier_for(followers):
    if followers >= 100_000: return "Signature"
    if followers >= 50_000:  return "Premier"
    if followers >= 10_000:  return "Established"
    if followers >= 5_000:   return "Rising"
    if followers >= 1_000:   return "Emerging"
    return "Starter"


# Physical-product gate. Placeholder numbers: set properly after market research.
GATE_MIN_RATING = 60
GATE_MIN_COMPLETED = 3
GATE_MIN_ENGAGEMENT = Decimal("2.0")   # % engagement rate
GATE_MIN_NZ_PCT = 50                   # % of followers in NZ

# Money. Placeholders: set properly after market research.
PLATFORM_FEE = Decimal("0.15")   # added on top for brands; creators keep 100%
PAYOUT_MIN = Decimal("20")       # creators are paid once earnings are over this
PAYOUT_WAIT_DAYS = 7             # view check: wait this long after posting before paying

# Location. Placeholders.
HOME_REGION_CHANGE_DAYS = 90     # home region can change once every 90 days
TRIP_MAX_DAYS = 30               # a trip can last at most this long
TRIP_MAX_UPCOMING = 3            # at most this many upcoming trips at once
TRIP_START_WITHIN_DAYS = 90      # a trip must start within this many days

# Until you've checked an account's insights, it counts as Starter, whatever it claims.
UNVERIFIED_COUNTS_AS_STARTER = True

PLATFORMS = [
    ("tiktok", "TikTok"),
    ("instagram", "Instagram"),
    ("youtube", "YouTube Shorts"),
    ("facebook", "Facebook"),
]

REGIONS = [
    ("northland", "Northland"),
    ("auckland", "Auckland"),
    ("waikato", "Waikato"),
    ("bay_of_plenty", "Bay of Plenty"),
    ("gisborne", "Gisborne"),
    ("hawkes_bay", "Hawke's Bay"),
    ("taranaki", "Taranaki"),
    ("manawatu_whanganui", "Manawatū-Whanganui"),
    ("wellington", "Wellington"),
    ("tasman_nelson", "Tasman & Nelson"),
    ("marlborough", "Marlborough"),
    ("west_coast", "West Coast"),
    ("canterbury", "Canterbury"),
    ("otago", "Otago (incl. Queenstown)"),
    ("southland", "Southland"),
]


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

    # Types where one creator may enter with several of their accounts
    MULTI_ACCOUNT_TYPES = {"views", "clipping", "affiliate"}

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
    platform = models.CharField(
        max_length=20, default="any",
        choices=[("any", "Any platform")] + PLATFORMS,
    )
    region = models.CharField(
        max_length=30, choices=REGIONS, blank=True, default="",
        help_text="Leave blank for online campaigns open to all of NZ.",
    )
    is_in_person = models.BooleanField(
        default=False, help_text="Creators have to go somewhere (a venue or an event).",
    )
    visit_from = models.DateField(null=True, blank=True, help_text="In-person: earliest visit date")
    visit_to = models.DateField(null=True, blank=True, help_text="In-person: latest visit date")
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

    @property
    def allows_multiple_accounts(self):
        return self.campaign_type in self.MULTI_ACCOUNT_TYPES

    @property
    def visit_window(self):
        """(start, end) dates when a creator needs to be in the campaign's region."""
        start = self.visit_from or timezone.localdate()
        end = self.visit_to or self.post_by
        return start, end

    def __str__(self):
        return self.name


class Creator(models.Model):
    """The person. Their social accounts live in SocialAccount.
    handle, followers, engagement_rate, nz_audience_pct and insights_checked are
    older fields kept for now; each account has its own copy."""
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
    region = models.CharField(
        max_length=30, choices=REGIONS, blank=True, default="",
        help_text="Home region. Local campaigns show to creators here.",
    )
    region_changed_at = models.DateTimeField(null=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="creator",
    )

    @property
    def tier(self):
        """Best tier across their accounts."""
        accounts = list(self.accounts.all())
        if not accounts:
            return tier_for(self.followers)
        return max((a.effective_tier for a in accounts), key=TIER_ORDER.index)

    @property
    def can_change_region(self):
        if self.region_changed_at is None:
            return True
        return timezone.now() >= self.region_changed_at + timedelta(days=HOME_REGION_CHANGE_DAYS)

    def ensure_account(self):
        """Every creator has at least one account. Older creators get theirs on first use."""
        account = self.accounts.first()
        if account is None:
            account = SocialAccount.objects.create(
                creator=self, platform="instagram", handle=self.handle,
                followers=self.followers, engagement_rate=self.engagement_rate,
                nz_audience_pct=self.nz_audience_pct, insights_checked=self.insights_checked,
            )
        # Applications made before accounts existed belong to the first account
        self.applications.filter(social_account__isnull=True).update(social_account=account)
        return account

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
        """What this creator still needs (using their closest account to passing)."""
        accounts = list(self.accounts.all())
        if not accounts:
            return SocialAccount(
                creator=self, followers=self.followers, engagement_rate=self.engagement_rate,
                nz_audience_pct=self.nz_audience_pct, insights_checked=self.insights_checked,
            ).product_gate_missing()
        return min((a.product_gate_missing() for a in accounts), key=len)

    @property
    def passes_product_gate(self):
        return not self.product_gate_missing()

    def __str__(self):
        return self.handle


class SocialAccount(models.Model):
    """One of a creator's social accounts. Tier and verification belong to the account."""
    creator = models.ForeignKey(Creator, on_delete=models.CASCADE, related_name="accounts")
    platform = models.CharField(max_length=20, choices=PLATFORMS, default="instagram")
    handle = models.CharField(max_length=60)
    followers = models.PositiveIntegerField(default=0)
    engagement_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Engagement % from this account's insights screenshots",
    )
    nz_audience_pct = models.PositiveSmallIntegerField(
        default=0, help_text="% of followers in NZ, from insights",
    )
    insights_checked = models.BooleanField(
        default=False, help_text="Tick once you've checked this account's insights screenshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["platform", "handle"], name="one_creator_per_account"),
        ]

    @property
    def tier(self):
        return tier_for(self.followers)

    @property
    def effective_tier(self):
        """The tier used for eligibility: unverified accounts count as Starter."""
        if UNVERIFIED_COUNTS_AS_STARTER and not self.insights_checked:
            return "Starter"
        return self.tier

    def product_gate_missing(self):
        """What this account's owner still needs before brands can send products."""
        creator = self.creator
        missing = []
        if creator.rating < GATE_MIN_RATING:
            missing.append(f"Rating {GATE_MIN_RATING}+ (you're at {creator.rating})")
        done = creator.completed_count
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

    def __str__(self):
        return f"{self.get_platform_display()} @{self.handle}"


class Trip(models.Model):
    """A creator travelling to another region. They also see that region's campaigns."""
    creator = models.ForeignKey(Creator, on_delete=models.CASCADE, related_name="trips")
    region = models.CharField(max_length=30, choices=REGIONS)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date"]

    def clean(self):
        if not (self.start_date and self.end_date):
            return
        today = timezone.localdate()
        if self.end_date < self.start_date:
            raise ValidationError("The end date can't be before the start date.")
        if (self.end_date - self.start_date).days > TRIP_MAX_DAYS:
            raise ValidationError(f"Trips can last at most {TRIP_MAX_DAYS} days.")
        if self.end_date < today:
            raise ValidationError("That trip is already over.")
        if self.start_date > today + timedelta(days=TRIP_START_WITHIN_DAYS):
            raise ValidationError(f"Trips must start within {TRIP_START_WITHIN_DAYS} days.")
        if self.creator_id:
            upcoming = Trip.objects.filter(creator_id=self.creator_id, end_date__gte=today)
            if upcoming.exclude(pk=self.pk).count() >= TRIP_MAX_UPCOMING:
                raise ValidationError(f"You can have at most {TRIP_MAX_UPCOMING} upcoming trips.")

    def __str__(self):
        return f"{self.creator} → {self.get_region_display()} ({self.start_date} to {self.end_date})"


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
    social_account = models.ForeignKey(
        SocialAccount, null=True, blank=True, on_delete=models.SET_NULL, related_name="applications",
    )
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
                fields=["social_account", "campaign"], name="one_application_per_account_campaign"
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