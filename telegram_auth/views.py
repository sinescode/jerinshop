import json
import secrets

from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .auth_utils import get_or_create_telegram_user, verify_init_data


@csrf_exempt
@require_POST
def tg_login(request):
    # Determine if this is an API call (JSON) or a form POST (browser navigation).
    is_json = request.content_type == 'application/json'

    if is_json:
        try:
            body = json.loads(request.body)
            init_data = body.get('init_data', '')
        except (json.JSONDecodeError, AttributeError):
            return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
        next_url = body.get('next', '/')
    else:
        init_data = request.POST.get('init_data', '')
        next_url = request.POST.get('next', '/')

    if not init_data:
        if is_json:
            return JsonResponse({'ok': False, 'error': 'Missing init_data'}, status=400)
        return redirect('/require-telegram/')

    user_data = verify_init_data(init_data)
    if not user_data:
        if is_json:
            return JsonResponse({'ok': False, 'error': 'Invalid or expired init data'}, status=403)
        return redirect('/require-telegram/')

    user, created = get_or_create_telegram_user(user_data)
    auth_login(request, user)

    # Generate a token for the tg_web_check cookie-based guard.
    # The client-side JS inside Telegram must keep this cookie alive.
    tg_token = secrets.token_urlsafe(32)
    request.session['tg_web_token'] = tg_token

    if is_json:
        response = JsonResponse({
            'ok': True,
            'created': created,
            'tg_web_token': tg_token,
            'user': {
                'id': user_data['id'],
                'display_name': user_data.get('username') or user_data.get('first_name', ''),
            },
        })
    else:
        response = redirect(next_url)

    # Set the tg_web_check cookie so the next request after navigation passes
    # the middleware check.  Short-lived (5 min) — JS inside Telegram refreshes
    # it every 30 s.
    response.set_cookie(
        'tg_web_check',
        tg_token,
        max_age=300,
        samesite='Lax',
        secure=request.is_secure(),
        httponly=False,
        path='/',
    )

    return response


@login_required
def profile(request):
    profile = request.user.telegram_profile
    from coins.models import Order

    orders_count = Order.objects.filter(user=request.user).count()

    return render(request, 'telegram_auth/profile.html', {
        'profile': profile,
        'orders_count': orders_count,
    })


@login_required
def history(request):
    from django.core.paginator import Paginator

    from coins.models import Order

    all_orders = Order.objects.filter(user=request.user).select_related('coin').prefetch_related('payments__payment_method').order_by('-created_at')
    total_order_count = all_orders.count()

    # Paginate orders — 3 per page
    paginator = Paginator(all_orders, 3)
    page_number = request.GET.get('page', 1)
    orders_page = paginator.get_page(page_number)

    return render(request, 'telegram_auth/history.html', {
        'orders_page': orders_page,
        'total_order_count': total_order_count,
    })
