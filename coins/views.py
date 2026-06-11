from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
import decimal
import hashlib
import logging
import threading
from io import BytesIO
import requests

logger = logging.getLogger(__name__)

SCREENSHOT_MAX_SIZE = 10 * 1024 * 1024  # 10 MB

from .models import (
    Coin, PriceTier,
    Order, OrderPayment, ReceiverAccount
)

from .telegram_bot import send_order_to_group, _build_message


@login_required
def coins_home(request):
    coins = Coin.objects.filter(is_active=True).order_by('order').prefetch_related('price_tiers', 'receiver_accounts')
    return render(request, 'coins/home.html', {'coins': coins})


@login_required
def coin_detail(request, coin_id):
    coin = get_object_or_404(Coin, pk=coin_id, is_active=True)
    tiers = coin.get_price_tiers()
    receiver_accounts = coin.receiver_accounts.all()
    return render(request, 'coins/coin_detail.html', {
        'coin': coin,
        'tiers': tiers,
        'receiver_accounts': receiver_accounts,
        'tiers_json': json.dumps([
            {
                'min': t.min_amount,
                'max': t.max_amount,
                'price_per_k': float(t.price_per_k),
                'label': t.display_range(),
            }
            for t in tiers
        ])
    })


@login_required
def order_form(request, coin_id):
    coin = get_object_or_404(Coin, pk=coin_id, is_active=True)
    tiers = coin.get_price_tiers()

    # Load user's saved payment methods — only these are shown in the form
    from payments.models import UserPaymentMethod
    saved_methods = UserPaymentMethod.objects.filter(
        user=request.user, is_active=True
    ).select_related('global_method')
    saved_methods_json = json.dumps([
        {
            'id': sm.pk,
            'global_method_id': sm.global_method_id,
            'account_number': sm.account_number,
            'display_name': sm.display_name,
        }
        for sm in saved_methods
    ])

    return render(request, 'coins/order_form.html', {
        'coin': coin,
        'tiers': tiers,
        'saved_methods_json': saved_methods_json,
        'tiers_json': json.dumps([
            {
                'min': t.min_amount,
                'max': t.max_amount,
                'price_per_k': float(t.price_per_k),
            }
            for t in tiers
        ])
    })


@login_required
def calculate_price(request):
    try:
        coin_id = int(request.GET.get('coin_id'))
        coin_amount = int(request.GET.get('amount', 0))
        coin = get_object_or_404(Coin, pk=coin_id, is_active=True)

        tier = coin.price_tiers.filter(
            min_amount__lte=coin_amount,
            max_amount__gte=coin_amount
        ).first()

        if not tier:
            return JsonResponse({'error': 'Amount out of range'}, status=400)

        total = decimal.Decimal(coin_amount) / 1000 * tier.price_per_k
        return JsonResponse({
            'total': float(total),
            'price_per_k': float(tier.price_per_k),
            'tier_label': tier.display_range(),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_POST
def submit_order(request, coin_id):
    coin = get_object_or_404(Coin, pk=coin_id, is_active=True)

    # Identity from verified Telegram session
    if request.user.is_authenticated and hasattr(request.user, 'telegram_profile'):
        profile = request.user.telegram_profile
        telegram_username = profile.username
        if telegram_username and not telegram_username.startswith('@'):
            telegram_username = '@' + telegram_username
        if not telegram_username:
            telegram_username = profile.display_name
    else:
        telegram_username = request.POST.get('telegram_username', '').strip().lstrip('@')

    sender_token = request.POST.get('sender_token', '').strip()

    # Enforce sender token if this coin requires it
    if coin.require_sender_token and not sender_token:
        messages.error(request, f'"{coin.sender_token_label}" is required for this coin.')
        return redirect('coins:order_form', coin_id=coin_id)

    coin_amount_k = request.POST.get('coin_amount', '0')
    try:
        coin_amount = int(float(coin_amount_k) * 1000)
    except (ValueError, TypeError):
        coin_amount = 0

    screenshot = request.FILES.get('screenshot')
    total_amount = decimal.Decimal(request.POST.get('total_amount', '0'))
    payment_data_raw = request.POST.get('payment_data', '[]')

    try:
        payment_data = json.loads(payment_data_raw)
    except json.JSONDecodeError:
        payment_data = []

    # ── Screenshot hash & duplicate check ────────────────────────────────────
    screenshot_hash = None
    if screenshot:
        if screenshot.size > SCREENSHOT_MAX_SIZE:
            messages.error(request, 'Screenshot must be under 10 MB.')
            return redirect('coins:order_form', coin_id=coin_id)

        hasher = hashlib.sha256()
        for chunk in screenshot.chunks():
            hasher.update(chunk)
        screenshot_hash = hasher.hexdigest()
        screenshot.seek(0)

        duplicate = Order.objects.filter(screenshot_hash=screenshot_hash).first()
        if duplicate:
            messages.error(
                request,
                'This screenshot has already been submitted. Please take a new screenshot.',
            )
            return redirect('coins:order_form', coin_id=coin_id)

    # ── Validate tier ─────────────────────────────────────────────────────────
    tier = coin.price_tiers.filter(
        min_amount__lte=coin_amount,
        max_amount__gte=coin_amount
    ).first()
    if not tier:
        messages.error(request, 'Coin amount is outside the allowed range.')
        return redirect('coins:order_form', coin_id=coin_id)

    recalc_total = decimal.Decimal(coin_amount) / 1000 * tier.price_per_k
    if recalc_total != total_amount:
        total_amount = recalc_total

    # ── Create order ──────────────────────────────────────────────────────────
    order = Order.objects.create(
        coin=coin,
        telegram_username=telegram_username,
        user=request.user if request.user.is_authenticated else None,
        sender_token=sender_token,
        coin_amount=coin_amount,
        total_amount=total_amount,
        screenshot_hash=screenshot_hash,
    )

    # Fetch user's saved payment methods for the selected ones
    saved_method_ids = [
        pd['saved_method_id'] for pd in payment_data
        if pd.get('saved_method_id')
    ]
    from payments.models import UserPaymentMethod
    saved_methods = {}
    if saved_method_ids:
        saved_methods = {
            sm.pk: sm
            for sm in UserPaymentMethod.objects.filter(
                pk__in=saved_method_ids, user=request.user
            ).select_related('global_method')
        }

    for pd in payment_data:
        saved_method_id = pd.get('saved_method_id')
        account_number = pd.get('account_number', '').strip()
        amount = decimal.Decimal(str(pd.get('amount', total_amount)))
        if not saved_method_id or not account_number:
            continue

        sm = saved_methods.get(saved_method_id)
        if sm:
            OrderPayment.objects.create(
                order=order,
                payment_method=sm.global_method,
                user_number=account_number,
                amount=amount,
            )

    # ── Fire Telegram notification in background ────────────────────────────
    # Build caption in main thread (warm DB connection); background thread
    # only handles network I/O so it never touches the ORM.
    if screenshot:
        screenshot_bytes = screenshot.read()
        screenshot_name = getattr(screenshot, 'name', 'screenshot.png')
        screenshot_content_type = getattr(screenshot, 'content_type', 'image/png')
        caption = _build_message(order)

        def _notify_telegram():
            try:
                file_id, _ = send_order_to_group(
                    order, BytesIO(screenshot_bytes),
                    screenshot_name, screenshot_content_type,
                    caption=caption,
                )
                if file_id:
                    from django.db import close_old_connections
                    close_old_connections()
                    order.screenshot_telegram_file_id = file_id
                    order.save(update_fields=['screenshot_telegram_file_id'])
            except Exception:
                logger.exception("Telegram notification failed for order %s", order.order_id)

        threading.Thread(target=_notify_telegram, daemon=True).start()

    return redirect('coins:order_success', order_id=order.order_id)


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, order_id=order_id)
    return render(request, 'coins/order_success.html', {'order': order})


def mask_username(username):
    if len(username) <= 2:
        return username[0] + '*' * (len(username) - 1) if len(username) > 1 else username
    return username[0] + '*' * (len(username) - 2) + username[-1]


def mask_number(number):
    if len(number) <= 3:
        return '*' * len(number)
    return '*' * (len(number) - 3) + number[-3:]


@login_required
def search_order(request):
    order = None
    error = None
    masked_payments = []
    masked_username = None
    query = request.GET.get('order_id', '').strip().lstrip('#')

    if query:
        try:
            order = Order.objects.select_related('coin').prefetch_related(
                'payments__payment_method'
            ).get(order_id__iexact=query)

            display_name = order.telegram_username
            if order.user and hasattr(order.user, 'telegram_profile'):
                display_name = order.user.telegram_profile.display_name
            masked_username = mask_username(display_name.lstrip('@'))
            for p in order.payments.all():
                masked_payments.append({
                    'method_name': p.payment_method.name,
                    'user_number': mask_number(p.user_number),
                })
        except Order.DoesNotExist:
            error = f'No order found with ID "{query}".'

    return render(request, 'coins/order_search.html', {
        'order': order,
        'error': error,
        'query': query,
        'masked_username': masked_username,
        'masked_payments': masked_payments,
    })


def _get_bot_token_for_order(order):
    """Extract the bot token from a stored screenshot_url if available."""
    import re
    if order.screenshot_url:
        m = re.search(r'/bot([^/]+)/', order.screenshot_url)
        if m:
            return m.group(1)
    from .telegram_bot import BOT_TOKEN
    return BOT_TOKEN


@login_required
def screenshot_proxy(request, order_id):
    """Proxy an order screenshot from Telegram. Extracts the correct bot token
    from screenshot_url so file_ids from previous bots still resolve."""
    qs = Order.objects.filter(order_id=order_id)
    if not request.user.is_staff:
        qs = qs.filter(user=request.user)
    order = get_object_or_404(qs)
    file_id = order.screenshot_telegram_file_id

    if not file_id:
        raise Http404("No screenshot available for this order")

    bot_token = _get_bot_token_for_order(order)
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getFile",
            params={"file_id": file_id},
            timeout=10,
        )
        if resp.status_code != 200:
            raise Http404("Could not retrieve screenshot from Telegram")

        file_path = resp.json().get("result", {}).get("file_path", "")
        if not file_path:
            raise Http404("Screenshot file not found on Telegram server")

        file_resp = requests.get(
            f"https://api.telegram.org/file/bot{bot_token}/{file_path}",
            timeout=30,
        )
        if file_resp.status_code != 200:
            raise Http404("Failed to download screenshot from Telegram")

        return HttpResponse(
            file_resp.content,
            content_type=file_resp.headers.get("content-type", "image/jpeg"),
        )
    except requests.exceptions.RequestException:
        raise Http404("Screenshot temporarily unavailable")