from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Campaign

def brand_required(view):
    """Only logged-in brands (or you as superuser) get through."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        brand = getattr(request.user, "brand_profile", None)
        if brand is None and not request.user.is_superuser:
            raise PermissionDenied  # creators land on a 403
        request.brand = brand
        return view(request, *args, **kwargs)
    return wrapper

def my_campaigns(request):
    """Brands see only their own campaigns. Superuser without a brand sees all."""
    qs = Campaign.objects.all()
    return qs if request.brand is None else qs.filter(brand=request.brand)