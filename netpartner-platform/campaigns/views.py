from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .access import brand_required, my_campaigns
from .eligibility import account_eligibility, eligible_campaigns
from .forms import BrandSignupForm, CampaignForm, CreatorSignupForm, ReviewForm
from .models import PAYOUT_MIN, PAYOUT_WAIT_DAYS, Application, Campaign, Creator, SocialAccount
from .rating import apply_review, on_status_change

TRACKER_STAGES = ["accepted", "drafting", "posted", "verified", "paid"]

# Button shown on each tracker column (moves the creator to the next stage).
# "verified" has no button: NetPartner marks creators paid from the Payouts page.
STAGE_BUTTONS = {
    "accepted": "Start drafting",
    "drafting": "Mark posted",
    "posted": "Verify post",
    "verified": None,
    "paid": None,
}

is_superuser = user_passes_test(lambda u: u.is_superuser)


def _total(queryset):
    return queryset.aggregate(t=Sum("amount"))["t"] or Decimal("0")


@login_required
def after_login(request):
    if hasattr(request.user, "brand_profile"):
        return redirect("home")
    if hasattr(request.user, "creator"):
        return redirect("creator_home")
    if request.user.is_superuser:
        return redirect("payouts")
    return redirect("/admin/")


# ---------- Sign up ----------

def creator_signup(request):
    if request.method == "POST":
        form = CreatorSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to NetPartner! Start with a campaign below to build your Rating.")
            return redirect("creator_home")
    else:
        form = CreatorSignupForm()
    return render(request, "campaigns/signup.html", {"form": form, "kind": "creator"})


def brand_signup(request):
    if request.method == "POST":
        form = BrandSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Create your first campaign to get started.")
            return redirect("home")
    else:
        form = BrandSignupForm()
    return render(request, "campaigns/signup.html", {"form": form, "kind": "brand"})


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
            messages.success(
                request,
                "Campaign submitted. We do a quick safety check, then it goes live to creators "
                "(usually within 2 working days).",
            )
            return redirect("campaign_detail", campaign_id=campaign.id)
    else:
        form = CampaignForm()
    return render(request, "campaigns/new_campaign.html", {"form": form})


@brand_required
def campaign_detail(request, campaign_id):
    campaign = get_object_or_404(my_campaigns(request), id=campaign_id)
    applications = Application.objects.filter(campaign=campaign).select_related("creator")
    accepted = applications.filter(status__in=TRACKER_STAGES)
    return render(request, "campaigns/campaign_detail.html", {
        "campaign": campaign,
        "applications": applications,
        "accepted_count": accepted.count(),
        "committed": _total(accepted),
    })


@brand_required
def update_application(request, application_id, action):
    application = get_object_or_404(
        Application, id=application_id, campaign__in=my_campaigns(request)
    )
    campaign = application.campaign

    if action == "accept":
        pay = campaign.pay_per_creator
        committed = _total(campaign.applications.filter(status__in=TRACKER_STAGES))
        if pay and committed + pay > campaign.budget:
            messages.error(request, "Accepting this creator would go over your budget.")
            return redirect("campaign_detail", campaign_id=campaign.id)
        application.status = Application.Status.ACCEPTED
        application.amount = pay
    elif action == "decline":
        application.status = Application.Status.REJECTED
    elif action == "advance":
        if not STAGE_BUTTONS.get(application.status):
            raise PermissionDenied  # only accepted, drafting and posted can move on
        next_index = TRACKER_STAGES.index(application.status) + 1
        application.status = TRACKER_STAGES[next_index]
    elif action == "missed":
        if application.status not in ("accepted", "drafting"):
            raise PermissionDenied  # only creators who haven't posted can miss
        application.status = Application.Status.MISSED
        application.amount = 0  # brands only pay for completed posts
    else:
        raise PermissionDenied

    application.save()
    on_status_change(application)

    if action in ("accept", "decline"):
        return redirect("campaign_detail", campaign_id=campaign.id)
    return redirect("campaign_tracker", campaign_id=campaign.id)


@brand_required
@require_POST
def review_creator(request, application_id):
    application = get_object_or_404(
        Application,
        id=application_id,
        campaign__in=my_campaigns(request),
        status__in=["verified", "paid"],
    )
    if hasattr(application, "review"):
        messages.info(request, "You've already reviewed this creator for this campaign.")
    else:
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.application = application
            review.save()
            apply_review(review)
            messages.success(request, f"Thanks! Review saved for @{application.creator.handle}.")
        else:
            messages.error(request, "Pick a star rating first.")
    return redirect("campaign_tracker", campaign_id=application.campaign_id)


@brand_required
def campaign_tracker(request, campaign_id):
    campaign = get_object_or_404(my_campaigns(request), id=campaign_id)
    applications = Application.objects.filter(campaign=campaign).select_related("creator", "review")
    labels = dict(Application.Status.choices)

    columns = [
        {
            "status": stage,
            "label": labels[stage],
            "apps": applications.filter(status=stage),
            "button": STAGE_BUTTONS[stage],
            "can_miss": stage in ("accepted", "drafting"),
            "can_review": stage in ("verified", "paid"),
        }
        for stage in TRACKER_STAGES
    ]

    return render(request, "campaigns/tracker.html", {
        "campaign": campaign,
        "columns": columns,
        "working_count": applications.filter(status__in=TRACKER_STAGES).count(),
        "posted_count": applications.filter(status__in=["posted", "verified", "paid"]).count(),
        "missed": applications.filter(status="missed"),
        "review_form": ReviewForm(),
    })


# ---------- Creator side ----------

def _pick_account(request, creator):
    """The social account the creator is looking through (?account=ID), else their first."""
    first = creator.ensure_account()
    account_id = request.POST.get("account") or request.GET.get("account")
    if account_id and str(account_id).isdigit():
        return get_object_or_404(SocialAccount, id=int(account_id), creator=creator)
    return first


@login_required
def creator_home(request):
    creator = get_object_or_404(Creator, user=request.user)
    account = _pick_account(request, creator)
    mine = Application.objects.filter(creator=creator)
    applied_ids = set(mine.filter(social_account=account).values_list("campaign_id", flat=True))

    # Creators only see campaigns this account can do (no locked list)
    available = [{"campaign": c, "reason": ""} for c in eligible_campaigns(account)]

    return render(request, "campaigns/creator_home.html", {
        "creator": creator,
        "account": account,
        "accounts": creator.accounts.all(),
        "available": available,
        "locked": [],
        "applied_ids": applied_ids,
        "gate_missing": account.product_gate_missing(),
        "rating_events": creator.rating_events.all()[:10],
        "earn_in_progress": _total(mine.filter(status__in=["accepted", "drafting", "posted"])),
        "earn_to_be_paid": _total(mine.filter(status="verified")),
        "earn_paid": _total(mine.filter(status="paid")),
    })


@login_required
def apply(request, campaign_id):
    creator = get_object_or_404(Creator, user=request.user)
    if creator.is_paused:
        messages.error(request, "You've missed 3 posts in 90 days, so applying is paused for 2 weeks.")
        return redirect("creator_home")
    campaign = get_object_or_404(Campaign, id=campaign_id, approved=True)
    account = _pick_account(request, creator)
    ok, reason = account_eligibility(account, campaign)
    if not ok:
        messages.error(request, f"You can't apply for {campaign.name} yet. {reason}.")
        return redirect("creator_home")
    Application.objects.get_or_create(
        campaign=campaign, social_account=account,
        defaults={"creator": creator, "status": Application.Status.PENDING},
    )
    messages.success(request, f"Applied for {campaign.name}. The brand will review your application.")
    return redirect(f"{reverse('creator_home')}?account={account.id}")


# ---------- NetPartner admin (Oli only) ----------

@is_superuser
def payouts(request):
    cutoff = timezone.now() - timedelta(days=PAYOUT_WAIT_DAYS)
    verified = Application.objects.filter(status="verified").select_related("creator", "campaign")

    rows = {}
    for app in verified.filter(posted_at__lte=cutoff):
        row = rows.setdefault(
            app.creator_id, {"creator": app.creator, "apps": [], "total": Decimal("0")}
        )
        row["apps"].append(app)
        row["total"] += app.amount

    return render(request, "campaigns/payouts.html", {
        "payable": [r for r in rows.values() if r["total"] >= PAYOUT_MIN],
        "below_min": [r for r in rows.values() if r["total"] < PAYOUT_MIN],
        "waiting": verified.exclude(posted_at__lte=cutoff),
        "payout_min": PAYOUT_MIN,
        "wait_days": PAYOUT_WAIT_DAYS,
        "unapproved": Campaign.objects.filter(approved=False).select_related("brand"),
    })


@is_superuser
@require_POST
def mark_paid(request, creator_id):
    cutoff = timezone.now() - timedelta(days=PAYOUT_WAIT_DAYS)
    apps = Application.objects.filter(
        creator_id=creator_id, status="verified", posted_at__lte=cutoff
    )
    total = _total(apps)
    count = 0
    for app in apps:
        app.status = Application.Status.PAID
        app.save()
        on_status_change(app)
        count += 1
    messages.success(request, f"Marked {count} post(s) paid (${total}).")
    return redirect("payouts")


@is_superuser
@require_POST
def approve_campaign(request, campaign_id):
    campaign = get_object_or_404(Campaign, id=campaign_id)
    campaign.approved = True
    campaign.save(update_fields=["approved"])
    messages.success(request, f"{campaign.name} is now live to creators.")
    return redirect("payouts")