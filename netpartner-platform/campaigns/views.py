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


@require_POST
def update_application(request, application_id, action):
    new_status = {"accept": "accepted", "decline": "rejected"}.get(action)
    if new_status is None:
        return redirect("home")

    application = get_object_or_404(Application, id=application_id)
    if application.status == "pending":
        application.status = new_status
        application.save()
    return redirect("campaign_detail", campaign_id=application.campaign_id)