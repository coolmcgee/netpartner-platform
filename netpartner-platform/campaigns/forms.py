from django import forms
from .models import Campaign

class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign                                   # build the form from the Campaign table
        fields = ["brand", "name", "brief", "budget", "post_by"]
        widgets = {"post_by": forms.DateInput(attrs={"type": "date"})}   # shows a date picker