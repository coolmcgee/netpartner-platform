from django.contrib import admin
from .models import Brand, Campaign, Creator, Application

admin.site.register(Brand)
admin.site.register(Campaign)
admin.site.register(Application)


@admin.register(Creator)
class CreatorAdmin(admin.ModelAdmin):
    list_display = ("__str__", "followers", "tier", "rating")