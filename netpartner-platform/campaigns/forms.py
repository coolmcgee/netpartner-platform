from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone

from .models import PLATFORMS, REGIONS, Brand, Campaign, Creator, Review, SocialAccount


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = [
            "name", "campaign_type", "brief", "budget", "pay_per_creator", "post_by",
            "platform", "region", "is_in_person", "visit_from", "visit_to",
        ]
        labels = {
            "name": "Campaign name",
            "campaign_type": "Campaign type",
            "budget": "Budget (NZD, before platform fee)",
            "pay_per_creator": "Pay per creator (NZD)",
            "post_by": "Creators post by",
            "platform": "Platform",
            "region": "Region (leave blank for online)",
            "is_in_person": "In person (creators have to go somewhere)",
            "visit_from": "Earliest visit date",
            "visit_to": "Latest visit date",
        }
        help_texts = {
            "pay_per_creator": "Each accepted creator gets this. Use 0 for gifted-only campaigns.",
            "region": "Only creators living in (or travelling to) this region will see it.",
        }
        widgets = {
            "brief": forms.Textarea(attrs={"rows": 5}),
            "post_by": forms.DateInput(attrs={"type": "date"}),
            "visit_from": forms.DateInput(attrs={"type": "date"}),
            "visit_to": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        data = super().clean()
        budget, pay = data.get("budget"), data.get("pay_per_creator")
        if budget is not None and pay and pay > budget:
            self.add_error("pay_per_creator", "Pay per creator can't be more than the whole budget.")
        if data.get("is_in_person"):
            if not data.get("region"):
                self.add_error("region", "Pick the region where creators need to go.")
            if not data.get("visit_from") or not data.get("visit_to"):
                self.add_error("visit_to", "Give the dates creators can visit.")
        start, end = data.get("visit_from"), data.get("visit_to")
        if start and end and end < start:
            self.add_error("visit_to", "The latest visit date can't be before the earliest.")
        return data


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["stars", "comment"]
        widgets = {"comment": forms.TextInput(attrs={"placeholder": "Optional comment"})}


class CreatorSignupForm(UserCreationForm):
    email = forms.EmailField()
    platform = forms.ChoiceField(choices=PLATFORMS, label="Main platform")
    handle = forms.CharField(max_length=60, help_text="Your main handle, e.g. aria.creates")
    niche = forms.CharField(max_length=50, help_text="What you post about, e.g. food, fitness")
    followers = forms.IntegerField(min_value=0, help_text="Followers on your main account")
    region = forms.ChoiceField(
        choices=[("", "Choose your region")] + REGIONS,
        help_text="Where you live. You can add trips later to see campaigns elsewhere.",
    )
    eligible = forms.BooleanField(
        label="I'm based in NZ and 18+, or 16–17 with a parent's permission",
    )

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def clean(self):
        data = super().clean()
        platform, handle = data.get("platform"), (data.get("handle") or "").lstrip("@")
        if platform and handle and SocialAccount.objects.filter(
            platform=platform, handle__iexact=handle
        ).exists():
            self.add_error("handle", "That account is already on NetPartner.")
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.save()
        handle = self.cleaned_data["handle"].lstrip("@")
        creator = Creator.objects.create(
            user=user,
            handle=handle,
            niche=self.cleaned_data["niche"],
            followers=self.cleaned_data["followers"],
            region=self.cleaned_data["region"],
            region_changed_at=timezone.now(),
        )
        SocialAccount.objects.create(
            creator=creator,
            platform=self.cleaned_data["platform"],
            handle=handle,
            followers=self.cleaned_data["followers"],
        )
        return user


class BrandSignupForm(UserCreationForm):
    email = forms.EmailField(label="Work email")
    brand_name = forms.CharField(max_length=100)
    website = forms.URLField(required=False, help_text="Website or Instagram link")

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.save()
        Brand.objects.create(
            user=user,
            name=self.cleaned_data["brand_name"],
            email=self.cleaned_data["email"],
            website=self.cleaned_data["website"],
        )
        return user