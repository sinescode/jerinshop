import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import AboutUsConfig, APKLink, ChannelLink, WorkMethod


@login_required
def all_links(request):
    return render(request, 'alllinks/links.html', {
        'apk_links': APKLink.objects.all(),
        'work_methods': WorkMethod.objects.all(),
        'channel_links': ChannelLink.objects.all(),
    })


@login_required
def work_methods(request):
    return render(request, 'alllinks/work_methods.html', {
        'work_methods': WorkMethod.objects.all(),
    })


@login_required
def apk_links(request):
    return render(request, 'alllinks/apk_links.html', {
        'apk_links': APKLink.objects.all(),
    })


@login_required
def channel_links(request):
    return render(request, 'alllinks/channel_links.html', {
        'channel_links': ChannelLink.objects.all(),
    })


@login_required
def about_us(request):
    config = AboutUsConfig.load()
    return render(request, 'alllinks/about_us.html', {'about_us': config})


def thumbnail_proxy(request, pk):
    """Proxy a WorkMethod thumbnail from Telegram without exposing the bot token."""
    method = get_object_or_404(WorkMethod, pk=pk)
    file_id = method.thumbnail_telegram_file_id
    if not file_id:
        raise Http404('No thumbnail available')

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        raise Http404('Telegram not configured')

    resp = requests.get(
        f'https://api.telegram.org/bot{token}/getFile',
        params={'file_id': file_id},
        timeout=10,
    )
    if resp.status_code != 200:
        raise Http404('Could not retrieve thumbnail from Telegram')

    file_path = resp.json().get('result', {}).get('file_path', '')
    if not file_path:
        raise Http404('Thumbnail file not found on Telegram server')

    file_resp = requests.get(
        f'https://api.telegram.org/file/bot{token}/{file_path}',
        timeout=30,
    )
    if file_resp.status_code != 200:
        raise Http404('Failed to download thumbnail from Telegram')

    return HttpResponse(
        file_resp.content,
        content_type=file_resp.headers.get('content-type', 'image/jpeg'),
    )
