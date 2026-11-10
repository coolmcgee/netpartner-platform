"""One place for "can this account do this campaign?". The dashboard list and the
Apply button both use it, so the rules can't drift apart."""
from .models import TIER_ORDER, Application, Campaign


def region_ok(creator, campaign):
    """Home region matches, or the creator has a trip there that overlaps the campaign."""
    if not campaign.region:
        return True, ""  # online: open to all of NZ
    if creator.region == campaign.region:
        return True, ""
    start, end = campaign.visit_window
    on_trip = creator.trips.filter(
        region=campaign.region, start_date__lte=end, end_date__gte=start
    ).exists()
    if on_trip:
        return True, ""
    return False, f"Only for creators in {campaign.get_region_display()}"


def account_eligibility(account, campaign):
    """Can this social account apply? Returns (True, "") or (False, reason)."""
    creator = account.creator
    if creator.is_paused:
        return False, "Applying is paused for now"
    if campaign.platform != "any" and campaign.platform != account.platform:
        return False, f"Needs a {campaign.get_platform_display()} account"
    if TIER_ORDER.index(account.effective_tier) < TIER_ORDER.index(campaign.min_tier):
        return False, f"Unlocks at {campaign.min_tier} tier"
    if campaign.needs_product:
        missing = account.product_gate_missing()
        if missing:
            return False, "Needs " + ", ".join(missing)
    ok, reason = region_ok(creator, campaign)
    if not ok:
        return False, reason
    if not campaign.allows_multiple_accounts:
        other = Application.objects.filter(creator=creator, campaign=campaign)
        if other.exclude(social_account=account).exists():
            return False, "You've already applied with another account"
    return True, ""


def eligible_campaigns(account):
    """Live campaigns this account can apply for (creators never see the rest)."""
    campaigns = Campaign.objects.filter(approved=True).select_related("brand").order_by("post_by")
    return [c for c in campaigns if account_eligibility(account, c)[0]]