from django.contrib import admin
from django.urls import path, include

from campaigns import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("after-login/", views.after_login, name="after_login"),

    # Sign up
    path("signup/creator/", views.creator_signup, name="creator_signup"),
    path("signup/brand/", views.brand_signup, name="brand_signup"),

    # Brand side
    path("", views.home, name="home"),
    path("new/", views.new_campaign, name="new_campaign"),
    path("campaign/<int:campaign_id>/", views.campaign_detail, name="campaign_detail"),
    path("campaign/<int:campaign_id>/tracker/", views.campaign_tracker, name="campaign_tracker"),
    path("application/<int:application_id>/<str:action>/", views.update_application, name="update_application"),
    path("review/<int:application_id>/", views.review_creator, name="review_creator"),

    # Creator side
    path("creator/", views.creator_home, name="creator_home"),
    path("campaign/<int:campaign_id>/apply/", views.apply, name="apply"),

    # NetPartner admin (Oli only)
    path("payouts/", views.payouts, name="payouts"),
    path("payouts/<int:creator_id>/pay/", views.mark_paid, name="mark_paid"),
    path("payouts/approve/<int:campaign_id>/", views.approve_campaign, name="approve_campaign"),
]