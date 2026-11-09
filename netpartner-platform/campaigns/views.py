from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404

from .access import brand_required, my_campaigns
from .forms import CampaignForm
from .models import Application, Campaign, Creator
from .rating import on_status_change

TRACKER_STAGES = ["accepted", "drafting", "posted", "verified", "paid"]

# Button shown on each tracker column (moves the creator to the next stage)
STAGE_BUTTONS = {
    "accepted": "Start drafting",
    "drafting": "Mark posted",
    "posted": "Verify post",
    "verified": "Mark paid",
    "paid": None,
}


@login_required
def after_login(request):
    if hasattr(request.user, "brand_profile"):
        return redirect("home")
    if hasattr(request.user, "creator"):
        return redirect("creator_home")
    return redirect("/admin/")


# ---------- Brand side ----------

@brand_required
def home(request):
    campaigns = my_campaigns(request)
    applications = Application.objects.filter(campaign__in=campaigns)
    return render(request, "campaigns/home.html", {
        "campaigns": campaigns,
        "applications": applications.order_by("-id")[:10],
        "pending": applications.filter(status="pending").count(),
        "active": applications.filter(status__in=TRACKER_STAGES[:-1]).count(),
    })


@brand_required
def new_campaign(request):
    if request.brand is None:
        raise PermissionDenied  # superuser with no Brand: create via /admin/
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.brand = request.brand
            campaign.save()
            return redirect("campaign_detail", campaign_id=campaign.id)
    else:
        form = CampaignForm()
    return render(request, "campaigns/new_campaign.html", {"form": form})


@brand_required
def campaign_detail(request, campaign_id):
    campaign = get_object_or_404(my_campaigns(request), id=campaign_id)
    applications = Application.objects.filter(campaign=campaign).select_related("creator")
    return render(request, "campaigns/campaign_detail.html", {
        "campaign": campaign,
        "applications": applications,
        "accepted_count": applications.filter(status__in=TRACKER_STAGES).count(),
    })


@brand_required
def update_application(request, application_id, action):
    application = get_object_or_404(
        Application, id=application_id, campaign__in=my_campaigns(request)
    )

    if action == "accept":
        application.status = Application.Status.ACCEPTED
    elif action == "decline":
        application.status = Application.Status.REJECTED
    elif action == "advance":
        if application.status not in TRACKER_STAGES[:-1]:
            raise PermissionDenied  # can't advance pending, rejected, missed or paid
        next_index = TRACKER_STAGES.index(application.status) + 1
        application.status = TRACKER_STAGES[next_index]
    elif action == "missed":
        if application.status not in ("accepted", "drafting"):
            raise PermissionDenied  # only creators who haven't posted can miss
        application.status = Application.Status.MISSED
    else:
        raise PermissionDenied

    application.save()
    on_status_change(application)

    if action in ("accept", "decline"):
        return redirect("campaign_detail", campaign_id=application.campaign.id)
    return redirect("campaign_tracker", campaign_id=application.campaign.id)


@brand_required
def campaign_tracker(request, campaign_id):
    campaign = get_object_or_404(my_campaigns(request), id=campaign_id)
    applications = Application.objects.filter(campaign=campaign).select_related("creator")
    labels = dict(Application.Status.choices)

    columns = [
        {
            "status": stage,
            "label": labels[stage],
            "apps": applications.filter(status=stage),
            "button": STAGE_BUTTONS[stage],
            "can_miss": stage in ("accepted", "drafting"),
        }
        for stage in TRACKER_STAGES
    ]

    return render(request, "campaigns/tracker.html", {
        "campaign": campaign,
        "columns": columns,
        "working_count": applications.filter(status__in=TRACKER_STAGES).count(),
        "posted_count": applications.filter(status__in=["posted", "verified", "paid"]).count(),
        "missed": applications.filter(status="missed"),
    })


# ---------- Creator side ----------

@login_required
def creator_home(request):
    creator = get_object_or_404(Creator, user=request.user)
    applied_ids = set(
        Application.objects.filter(creator=creator).values_list("campaign_id", flat=True)
    )
    return render(request, "campaigns/creator_home.html", {
        "creator": creator,
        "campaigns": Campaign.objects.all(),
        "applied_ids": applied_ids,
        "rating_events": creator.rating_events.all()[:10],
    })


@login_required
def apply(request, campaign_id):
    creator = get_object_or_404(Creator, user=request.user)
    if creator.is_paused:
        messages.error(request, "You've missed 3 posts in 90 days, so applying is paused for 2 weeks.")
        return redirect("creator_home")
    campaign = get_object_or_404(Campaign, id=campaign_id)
    Application.objects.get_or_create(
        campaign=campaign, creator=creator,
        defaults={"status": Application.Status.PENDING},
    )
    return redirect("creator_home")