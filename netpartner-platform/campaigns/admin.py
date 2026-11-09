from django.contrib import admin

from .models import Application, Brand, Campaign, Creator, RatingEvent, Review

admin.site.register(Brand)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "campaign_type", "budget", "pay_per_creator", "post_by", "approved")
    list_filter = ("approved", "campaign_type")
    list_editable = ("approved",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("creator", "campaign", "status", "amount", "posted_at")
    list_filter = ("status",)


class RatingEventInline(admin.TabularInline):
    model = RatingEvent
    extra = 0
    readonly_fields = ("change", "reason", "application", "created_at")


@admin.register(Creator)
class CreatorAdmin(admin.ModelAdmin):
    list_display = (
        "__str__", "followers", "tier", "rating",
        "engagement_rate", "nz_audience_pct", "insights_checked", "product_gate",
    )
    list_filter = ("insights_checked",)
    inlines = [RatingEventInline]

    @admin.display(boolean=True, description="Product gate")
    def product_gate(self, obj):
        return obj.passes_product_gate


@admin.register(RatingEvent)
class RatingEventAdmin(admin.ModelAdmin):
    list_display = ("creator", "change", "reason", "created_at")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("application", "stars", "comment", "created_at")