from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


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
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="campaigns")
    name = models.CharField(max_length=100)
    brief = models.TextField()
    budget = models.DecimalField(max_digits=10, decimal_places=2)
    post_by = models.DateField()

    def __str__(self):
        return self.name


class Creator(models.Model):
    handle = models.CharField(max_length=60)          # e.g. @aria.creates
    niche = models.CharField(max_length=50)
    followers = models.PositiveIntegerField(default=0)
    rating = models.PositiveIntegerField(default=50)  # everyone starts at 50
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