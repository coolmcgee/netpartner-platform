from django.db import models

class Brand(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    website = models.URLField(blank=True)


    def __str__(self):
        return self.name

class Campaign(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='campaigns')

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

    @property
    def tier(self):
        if self.followers < 1000:
            return "Starter"
        if self.followers < 5000:
            return "Emerging"
        if self.followers < 10000:
            return "Rising"
        if self.followers < 50000:
            return "Established"
        if self.followers < 100000:
            return "Premier"
        return "Signature"

    def __str__(self):
        return self.handle


class Application(models.Model):
    # Your state machine: the only allowed values for status
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
    applied_at = models.DateTimeField(auto_now_add=True)   # filled in automatically

    def __str__(self):
        return f"{self.creator} → {self.campaign} ({self.status})"

