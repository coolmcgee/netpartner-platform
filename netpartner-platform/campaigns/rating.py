from datetime import timedelta

from django.utils import timezone

from .models import RatingEvent

# Placeholder values: tune after market research
POINTS = {
    "on_time": 5,     # completed, posted by the deadline
    "late": 1,        # completed, within 24h after the deadline
    "very_late": -2,  # completed, more than 24h late
    "missed": -10,    # never posted
}

# Brand review stars -> Rating change
REVIEW_POINTS = {5: 3, 4: 1, 3: 0, 2: -2, 1: -4}


def change_rating(creator, application, change, reason):
    """Adjust a creator's Rating once per application per reason, and log it."""
    if RatingEvent.objects.filter(application=application, reason=reason).exists():
        return  # already applied, so don't double count
    creator.rating = max(0, min(100, creator.rating + change))
    creator.save(update_fields=["rating"])
    RatingEvent.objects.create(
        creator=creator, application=application, change=change, reason=reason
    )


def on_status_change(application):
    """Call after an application's status is saved."""
    status = application.status
    creator = application.creator

    if status == "posted" and application.posted_at is None:
        application.posted_at = timezone.now()
        application.save(update_fields=["posted_at"])

    elif status == "verified":
        posted_day = timezone.localtime(application.posted_at or timezone.now()).date()
        deadline = application.campaign.post_by
        if posted_day <= deadline:
            change_rating(creator, application, POINTS["on_time"], "On-time post")
        elif posted_day <= deadline + timedelta(days=1):
            change_rating(creator, application, POINTS["late"], "Late post (within 24h)")
        else:
            change_rating(creator, application, POINTS["very_late"], "Late post")

    elif status == "missed":
        change_rating(creator, application, POINTS["missed"], "Missed post")


def apply_review(review):
    """Call after a brand leaves a review."""
    change = REVIEW_POINTS.get(review.stars, 0)
    change_rating(
        review.application.creator, review.application, change, f"Brand review ({review.stars}★)"
    )