from django.contrib import admin

from .models import Application, Brand, Campaign, Creator, RatingEvent, Review, SocialAccount, Trip

admin.site.register(Brand)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name", "brand", "campaign_type", "platform", "region",
        "budget", "pay_per_creator", "post_by", "approved",
    )
    list_filter = ("approved", "campaign_type", "platform")
    list_editable = ("approved",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("creator", "social_account", "campaign", "status", "amount", "posted_at")
    list_filter = ("status",)


class RatingEventInline(admin.TabularInline):
    model = RatingEvent
    extra = 0
    readonly_fields = ("change", "reason", "application", "created_at")


class SocialAccountInline(admin.TabularInline):
    model = SocialAccount
    extra = 0
    fields = ("platform", "handle", "followers", "engagement_rate", "nz_audience_pct", "insights_checked")


class TripInline(admin.TabularInline):
    model = Trip
    extra = 0


@admin.register(Creator)
class CreatorAdmin(admin.ModelAdmin):
    list_display = ("__str__", "region", "tier", "rating", "account_count", "product_gate")
    list_filter = ("region",)
    inlines = [SocialAccountInline, TripInline, RatingEventInline]

    @admin.display(description="Accounts")
    def account_count(self, obj):
        return obj.accounts.count()

    @admin.display(boolean=True, description="Product gate")
    def product_gate(self, obj):
        return obj.passes_product_gate


@admin.register(SocialAccount)
class SocialAccountAdmin(admin.ModelAdmin):
    list_display = ("__str__", "creator", "followers", "engagement_rate", "nz_audience_pct", "insights_checked")
    list_filter = ("platform", "insights_checked")
    list_editable = ("insights_checked",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("creator", "region", "start_date", "end_date")


@admin.register(RatingEvent)
class RatingEventAdmin(admin.ModelAdmin):
    list_display = ("creator", "change", "reason", "created_at")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("application", "stars", "comment", "created_at")