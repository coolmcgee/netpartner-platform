from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Sum
from .models import Campaign, Application
from .forms import CampaignForm


def home(request):
    campaigns = (
        Campaign.objects.select_related("brand")
        .annotate(
            applicant_count=Count("applications"),
            pending_count=Count("applications", filter=Q(applications__status="pending")),
        )
        .order_by("post_by")
    )
    return render(request, "campaigns/home.html", {
        "campaigns": campaigns,
        "pending_total": Application.objects.filter(status="pending").count(),
        "accepted_total": Application.objects.filter(status="accepted").count(),
        "total_budget": Campaign.objects.aggregate(total=Sum("budget"))["total"] or 0,
    })


def new_campaign(request):
    if request.method == "POST":
        form = CampaignForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("home")
    else:
        form = CampaignForm()
    return render(request, "campaigns/new_campaign.html", {"form": form})


def campaign_detail(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    applications = (
        Application.objects.filter(campaign=campaign)
        .select_related("creator")
        .order_by("-applied_at")
    )
    return render(request, "campaigns/campaign_detail.html", {
        "campaign": campaign,
        "applications": applications,
        "accepted_count": applications.filter(status="accepted").count(),
    })


# Tracker columns: (status, column title, button label to move to the next stage)
TRACKER_STAGES = [
    ("accepted", "Accepted", "Start drafting"),
    ("drafting", "Drafting", "Mark posted"),
    ("posted", "Posted", "Verify post"),
    ("verified", "Verified", "Mark paid"),
    ("paid", "Paid", None),
]

NEXT_STATUS = {
    "accepted": "drafting",
    "drafting": "posted",
    "posted": "verified",
    "verified": "paid",
}


def campaign_tracker(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    apps = list(campaign.applications.select_related("creator"))

    columns = [
        {
            "status": status,
            "label": label,
            "button": button,
            "apps": [a for a in apps if a.status == status],
        }
        for status, label, button in TRACKER_STAGES
    ]

    return render(request, "campaigns/tracker.html", {
        "campaign": campaign,
        "columns": columns,
        "working_count": sum(len(c["apps"]) for c in columns),
        "posted_count": sum(1 for a in apps if a.status in ("posted", "verified", "paid")),
    })


@require_POST
def update_application(request, application_id, action):
    application = get_object_or_404(Application, id=application_id)

    # Accept / decline on the applicants page
    if action in ("accept", "decline"):
        if application.status == "pending":
            application.status = "accepted" if action == "accept" else "rejected"
            application.save()
        return redirect("campaign_detail", campaign_id=application.campaign_id)

    # Move one stage along on the tracker
    if action == "advance":
        next_status = NEXT_STATUS.get(application.status)
        if next_status:
            application.status = next_status
            application.save()
        return redirect("campaign_tracker", campaign_id=application.campaign_id)

    return redirect("home")