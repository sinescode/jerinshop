import json
import logging
import secrets

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from .models import Order
from .telegram_bot import build_keyboard, answer_callback, edit_message_caption, _build_message, send_start_message, send_order_status_notification

logger = logging.getLogger(__name__)


@csrf_exempt
def telegram_webhook(request):
    """Receives all updates from Telegram — handles /start, text messages, and callback queries."""

    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)

    # Verify the request originated from Telegram
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if expected:
        header = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not secrets.compare_digest(header, expected):
            logger.warning("Webhook rejected: invalid secret token")
            return JsonResponse({'ok': False}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        logger.warning("Webhook received invalid JSON")
        return JsonResponse({'ok': False}, status=400)

    # -- Handle /start command and text messages --
    message = data.get('message')
    if message:
        text = (message.get('text') or '').strip()
        chat_id = message.get('chat', {}).get('id')
        logger.info(f"WEBHOOK MESSAGE: text='{text}' chat_id={chat_id}")
        if chat_id:
            send_start_message(chat_id)
        return JsonResponse({'ok': True})

    # -- Handle button presses (callback queries) --
    callback = data.get('callback_query')
    if not callback:
        return JsonResponse({'ok': True})

    callback_id  = callback['id']
    chat_id      = callback['message']['chat']['id']
    message_id   = callback['message']['message_id']
    cb_data      = callback.get('data', '')

    logger.info("Callback received: %s", cb_data)

    # ── Parse callback data ───────────────────────────────────────────────────
    if ':' not in cb_data:
        answer_callback(callback_id, 'Unknown action.')
        return JsonResponse({'ok': True})

    action, order_id = cb_data.split(':', 1)

    if action not in ('approve', 'reject'):
        answer_callback(callback_id, 'Unknown action.')
        return JsonResponse({'ok': True})

    # ── Fetch order from DB ───────────────────────────────────────────────────
    try:
        order = Order.objects.get(order_id=order_id)
    except Order.DoesNotExist:
        logger.warning("Callback for unknown order_id: %s", order_id)
        answer_callback(callback_id, 'Order not found.')
        return JsonResponse({'ok': True})

    # ── Apply action ──────────────────────────────────────────────────────────
    if action == 'approve':
        order.status = 'approved'
        order.save(update_fields=['status'])
        new_keyboard = build_keyboard(order_id, active='approved')
        answer_callback(callback_id, 'Order approved!')
        logger.info("Order %s approved via Telegram", order_id)

        # Notify the user personally
        order_refreshed = Order.objects.filter(pk=order.pk).select_related(
            'user__telegram_profile', 'coin'
        ).first()
        if order_refreshed:
            send_order_status_notification(order_refreshed)

    elif action == 'reject':
        order.status = 'cancelled'
        order.save(update_fields=['status'])
        new_keyboard = build_keyboard(order_id, active='rejected')
        answer_callback(callback_id, 'Order rejected.')
        logger.info("Order %s rejected via Telegram", order_id)

        # Notify the user personally
        order_refreshed = Order.objects.filter(pk=order.pk).select_related(
            'user__telegram_profile', 'coin'
        ).first()
        if order_refreshed:
            send_order_status_notification(order_refreshed)

    # ── Update message caption + keyboard in Telegram ──────────────────────────
    edit_message_caption(chat_id, message_id, _build_message(order), new_keyboard)

    return JsonResponse({'ok': True})