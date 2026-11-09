from django.contrib import admin
from django.urls import path
from campaigns import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("new/", views.new_campaign, name="new_campaign"),
    path("campaign/<int:campaign_id>/", views.campaign_detail, name="campaign_detail"),
    path("application/<int:application_id>/<str:action>/", views.update_application, name="update_application"),
    path("campaign/<int:campaign_id>/tracker/", views.campaign_tracker, name="campaign_tracker"),
]