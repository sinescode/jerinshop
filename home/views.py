from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import HomeButton


@login_required
def home(request):
    buttons = HomeButton.objects.filter(is_active=True).order_by('order')
    return render(request, 'home/home.html', {'buttons': buttons})


def require_telegram(request):
    return render(request, 'home/require_telegram.html')


def banned(request):
    profile = None
    if request.user.is_authenticated and hasattr(request.user, 'telegram_profile'):
        profile = request.user.telegram_profile
    return render(request, 'home/banned.html', {'profile': profile})