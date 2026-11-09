from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Brand, Campaign, Creator, Review


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "campaign_type", "brief", "budget", "pay_per_creator", "post_by"]
        labels = {
            "name": "Campaign name",
            "campaign_type": "Campaign type",
            "budget": "Budget (NZD, before platform fee)",
            "pay_per_creator": "Pay per creator (NZD)",
            "post_by": "Creators post by",
        }
        help_texts = {
            "pay_per_creator": "Each accepted creator gets this. Use 0 for gifted-only campaigns.",
        }
        widgets = {
            "brief": forms.Textarea(attrs={"rows": 5}),
            "post_by": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        data = super().clean()
        budget, pay = data.get("budget"), data.get("pay_per_creator")
        if budget is not None and pay and pay > budget:
            self.add_error("pay_per_creator", "Pay per creator can't be more than the whole budget.")
        return data


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["stars", "comment"]
        widgets = {"comment": forms.TextInput(attrs={"placeholder": "Optional comment"})}


class CreatorSignupForm(UserCreationForm):
    email = forms.EmailField()
    handle = forms.CharField(max_length=60, help_text="Your main handle, e.g. aria.creates")
    niche = forms.CharField(max_length=50, help_text="What you post about, e.g. food, fitness")
    followers = forms.IntegerField(min_value=0, help_text="Followers on your main platform")
    eligible = forms.BooleanField(
        label="I'm based in NZ and 18+, or 16–17 with a parent's permission",
    )

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.save()
        Creator.objects.create(
            user=user,
            handle=self.cleaned_data["handle"].lstrip("@"),
            niche=self.cleaned_data["niche"],
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