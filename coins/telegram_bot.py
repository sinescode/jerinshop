import json
import re
import requests
import logging
from io import BytesIO
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# MarkdownV2 reserved chars that need escaping when not used as formatting
_MDV2_ESCAPE_RE = re.compile(r'[_*\[\]()~`>#+\-=|{}.!]')


def _escape_mdv2(text):
    """Escape MarkdownV2 reserved characters. Preserves intentional formatting."""
    # Protect code blocks (``` ... ```)
    code_blocks = []

    def _protect_code(m):
        code_blocks.append(m.group(0))
        return f'\x00CODE{len(code_blocks) - 1}\x00'

    text = re.sub(r'```.*?```', _protect_code, text, flags=re.DOTALL)

    # Protect intentional bold (*text*)
    bold_spans = []

    def _protect_bold(m):
        bold_spans.append(m.group(0))
        return f'\x00BOLD{len(bold_spans) - 1}\x00'

    text = re.sub(r'\*[^*]+\*', _protect_bold, text)

    # Escape remaining reserved chars
    text = _MDV2_ESCAPE_RE.sub(r'\\\g<0>', text)

    # Restore bold spans (escape inner text, keep * markers as formatting)
    for i, span in enumerate(bold_spans):
        inner = span[1:-1]  # strip * *
        escaped_inner = _MDV2_ESCAPE_RE.sub(r'\\\g<0>', inner)
        text = text.replace(f'\x00BOLD{i}\x00', f'*{escaped_inner}*')

    # Restore code blocks (un-escape everything inside)
    for i, block in enumerate(code_blocks):
        text = text.replace(f'\x00CODE{i}\x00', block)

    return text


BOT_TOKEN = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
GROUP_CHAT_ID = getattr(settings, 'TELEGRAM_GROUP_CHAT_ID', '')
GROUP_CHAT_ID2 = getattr(settings, 'TELEGRAM_GROUP_CHAT_ID2', '')
TELEGRAM_PHOTO_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MB

# ── Session ───────────────────────────────────────────────────────────────────
_telegram_session = requests.Session()
_retry_strategy = Retry(
    total=2,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST", "GET"],
    raise_on_status=False,
)
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_telegram_session.mount("https://", _adapter)

if hasattr(settings, 'TELEGRAM_PROXY') and settings.TELEGRAM_PROXY:
    _telegram_session.proxies = {
        "http": settings.TELEGRAM_PROXY,
        "https": settings.TELEGRAM_PROXY,
    }


def _md(text: str) -> str:
    """Escape special chars for Markdown v1."""
    for ch in ('_', '*', '[', '`'):
        text = str(text).replace(ch, f'\\{ch}')
    return text


def build_keyboard(order_id: str, active: str = None) -> dict:
    """
    Build inline keyboard for approve/reject actions.
    active='approved' → Approve button locked, Reject button free
    active='rejected' → Reject button locked, Approve button free
    active=None       → Both buttons free (initial state on new order)
    """
    approve_text = '✅ Approved' if active == 'approved' else '✅ Approve'
    reject_text  = '❌ Rejected' if active == 'rejected' else '❌ Reject'

    return {
        'inline_keyboard': [[
            {'text': approve_text, 'callback_data': f'approve:{order_id}'},
            {'text': reject_text,  'callback_data': f'reject:{order_id}'},
        ]]
    }


def answer_callback(callback_id: str, text: str) -> None:
    """Answer a Telegram callback query to remove the loading spinner."""
    try:
        _telegram_session.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery',
            json={'callback_query_id': callback_id, 'text': text},
            timeout=5,
        )
    except Exception as e:
        logger.warning("answerCallbackQuery failed: %s", e)


def edit_keyboard(chat_id, message_id: int, keyboard: dict) -> None:
    """Edit the inline keyboard of an existing Telegram message."""
    try:
        resp = _telegram_session.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup',
            json={
                'chat_id': chat_id,
                'message_id': message_id,
                'reply_markup': keyboard,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("editMessageReplyMarkup failed: %s", resp.text[:200])
    except Exception as e:
        logger.warning("editMessageReplyMarkup exception: %s", e)


def edit_message_text(chat_id, message_id: int, text: str, keyboard: dict) -> None:
    """Edit both text and keyboard of an existing Telegram message."""
    try:
        resp = _telegram_session.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageText',
            json={
                'chat_id': chat_id,
                'message_id': message_id,
                'text': text,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True,
                'reply_markup': keyboard,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("editMessageText failed: %s", resp.text[:200])
    except Exception as e:
        logger.warning("editMessageText exception: %s", e)


def edit_message_caption(chat_id, message_id: int, caption: str, keyboard: dict) -> None:
    """Edit caption and keyboard of a photo message."""
    try:
        resp = _telegram_session.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageCaption',
            json={
                'chat_id': chat_id,
                'message_id': message_id,
                'caption': caption,
                'parse_mode': 'Markdown',
                'reply_markup': keyboard,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            logger.warning("editMessageCaption failed: %s", resp.text[:200])
    except Exception as e:
        logger.warning("editMessageCaption exception: %s", e)


def _build_message(order) -> str:
    """Simple, clean Markdown message — safe within 4096 char text limit."""

    # Payments
    payment_lines = []
    for p in order.payments.select_related('payment_method').all():
        payment_lines.append(f"  {_md(p.payment_method.name)}: `{_md(p.user_number)}`")
    payments_str = '\n'.join(payment_lines) if payment_lines else "  _None recorded_"

    # Sender / coupon token
    sender_line = ''
    if order.sender_token:
        label = _md(order.coin.sender_token_label or 'Sender Token') if order.coin_id else 'Sender Token'
        sender_line = f"{label}: `{_md(order.sender_token)}`\n"

    # Amount
    raw_k = order.coin_amount / 1000
    amount_display = f"{int(raw_k)}K" if raw_k == int(raw_k) else f"{raw_k:.2f}K"

    # Telegram user ID — get from profile if available
    tg_id_str = ''
    if order.user_id and hasattr(order.user, 'telegram_profile'):
        tg_id = order.user.telegram_profile.telegram_id
        tg_id_str = f"`{tg_id}`"

    # Status
    status_map = {
        'approved':  'Approved',
        'rejected':  'Rejected',
        'cancelled': 'Cancelled',
        'pending':   'Pending',
    }
    status_display = status_map.get(order.status, 'Pending')

    status_emoji = {
        'approved': '✅', 'rejected': '❌',
        'cancelled': '❌', 'pending': '⏳',
    }.get(order.status, '⏳')

    user_id_line = f"\n🆔 *ID:* {tg_id_str}\n" if tg_id_str else "\n"

    return (
        f"{status_emoji} *New Order* `#{order.order_id}`\n"
        f"\n"
        f"👤 *User:* {_md(order.telegram_username)}{user_id_line}"
        f"💰 *Coin:* {_md(order.coin.name)}\n"
        f"📊 *Amount:* `{amount_display}`\n"
        f"{sender_line}"
        f"\n"
        f"💳 *Payments:*\n{payments_str}\n"
        f"\n"
        f"💵 *Total:* `৳ {order.total_amount}`\n"
        f"{status_emoji} {status_display}  •  _{order.created_at.strftime('%b %d, %Y %H:%M')}_"
    )


def _send_photo_then_message(order_id, caption, file_bytes, file_name, content_type) -> tuple:
    """Send photo with full caption + Approve/Reject keyboard in a single API call."""

    photo_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        resp = _telegram_session.post(
            photo_url,
            data={
                'chat_id': GROUP_CHAT_ID,
                'caption': caption,
                'parse_mode': 'Markdown',
                'reply_markup': json.dumps(build_keyboard(order_id)),
            },
            files={'photo': (file_name, BytesIO(file_bytes), content_type)},
            timeout=(5, 20),
        )
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection failed for order %s: %s", order_id, e)
        return None, None
    except requests.exceptions.Timeout as e:
        logger.error("Timeout sending photo for order %s: %s", order_id, e)
        return None, None
    except Exception as e:
        logger.exception("Unexpected error sending photo for order %s: %s", order_id, e)
        return None, None

    if resp.status_code != 200:
        logger.error("sendPhoto failed for order %s: status=%d body=%s",
                     order_id, resp.status_code, resp.text[:300])
        return None, None

    try:
        result = resp.json().get('result', {})
        photos = result.get('photo', [])
        file_id = photos[-1]['file_id'] if photos else ''
        public_url = get_file_url(file_id) if file_id else ''
    except (ValueError, KeyError) as e:
        logger.error("JSON parse error after sendPhoto for order %s: %s", order_id, e)
        return '', ''

    logger.info("Photo with full caption sent for order %s. file_id=%s", order_id, file_id)
    return file_id, public_url


def _send_text_fallback(order, error_reason: str) -> bool:
    """Send full styled text message with keyboard when photo upload fails."""
    text = (
        _build_message(order)
        + f"\n\n_Screenshot unavailable: {_md(error_reason)}_"
    )
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        resp = _telegram_session.post(
            url,
            json={
                'chat_id': GROUP_CHAT_ID,
                'text': text,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True,
                'reply_markup': build_keyboard(order.order_id),
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.warning("Fallback text sent for order %s (reason: %s)", order.order_id, error_reason)
            return True
        logger.error("Fallback sendMessage failed: status=%d body=%s", resp.status_code, resp.text)
    except Exception as e:
        logger.exception("Fallback message exception for order %s: %s", order.order_id, e)
    return False


def send_order_to_group(order, screenshot_file, file_name=None, content_type=None, caption=None):
    """
    Send order + screenshot to Telegram group.
    Returns: (file_id, public_url) on success, or ('', '') on total failure.

    caption, if provided, is used directly (pre-built in the main thread to avoid
    DB queries in the background thread). If omitted, it is built from the order.
    """
    if not BOT_TOKEN or not GROUP_CHAT_ID:
        logger.error("Telegram not configured: BOT_TOKEN=%r, GROUP_CHAT_ID=%r", BOT_TOKEN, GROUP_CHAT_ID)
        return '', ''

    if caption is None:
        caption = _build_message(order)

    # ── File size check ───────────────────────────────────────────────────────
    screenshot_file.seek(0, 2)
    file_size = screenshot_file.tell()
    screenshot_file.seek(0)

    if file_size > TELEGRAM_PHOTO_SIZE_LIMIT:
        logger.warning("Screenshot too large (%d bytes) for order %s", file_size, order.order_id)
        _send_text_fallback(order, "Image exceeds 10 MB limit")
        return '', ''

    file_bytes = screenshot_file.read()
    if file_name is None:
        file_name = getattr(screenshot_file, 'name', 'screenshot.png')
    if content_type is None:
        content_type = getattr(screenshot_file, 'content_type', 'image/png')

    file_id, public_url = _send_photo_then_message(order.order_id, caption, file_bytes, file_name, content_type)

    if file_id is None:
        _send_text_fallback(order, "Photo upload failed")
        return '', ''

    return file_id, public_url


def get_file_url(file_id: str) -> str:
    """Get public URL for a Telegram file_id."""
    if not BOT_TOKEN or not file_id:
        return ''
    try:
        r = _telegram_session.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
            params={'file_id': file_id},
            timeout=10,
        )
        if r.status_code == 200:
            path = r.json().get('result', {}).get('file_path', '')
            if path:
                return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{path}"
    except Exception as e:
        logger.error("getFile failed for %s: %s", file_id, e)
    return ''


def send_order_status_notification(order):
    """
    Send a stylish Telegram message to the user when their order is approved or cancelled.

    Uses order.user.telegram_profile.telegram_id as the destination chat_id.
    Gracefully handles missing profiles, missing chat_ids, and network errors.
    Returns True on success, False on failure.
    """
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN not configured, cannot send order notification")
        return False

    # ── Resolve chat_id ────────────────────────────────────────────────────
    if not order.user_id or not hasattr(order.user, 'telegram_profile'):
        logger.warning(
            "Order %s has no associated user or telegram_profile — skipping notification",
            order.order_id,
        )
        return False

    chat_id = order.user.telegram_profile.telegram_id
    if not chat_id:
        logger.warning("Order %s user has no telegram_id — skipping notification", order.order_id)
        return False

    # ── Build stylish message ──────────────────────────────────────────────
    status_emoji = '✅' if order.status == 'approved' else '❌'
    status_text = 'Approved' if order.status == 'approved' else 'Cancelled'

    raw_k = order.coin_amount / 1000
    amount_display = f"{int(raw_k)}K" if raw_k == int(raw_k) else f"{raw_k:.2f}K"

    text = (
        f"\U0001FA99 *Coin Order Update*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"\U0001F4CB Order ID: `#{order.order_id}`\n"
        f"\U0001F4C5 Date: {order.created_at.strftime('%Y-%m-%d')}\n"
        f"\U0001F4B0 Amount: {amount_display} {_md(order.coin.name)}\n"
        f"\U0001F4B5 Price: \U000009F3{order.total_amount}\n"
        f"\U0001F4CA Status: {status_emoji} {status_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Thank you for your order! \U0001F389"
    )

    try:
        resp = _telegram_session.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Order status notification sent for %s to chat_id %s", order.order_id, chat_id)
            return True
        else:
            logger.warning(
                "Failed to send order status notification for %s (chat_id=%s): %s",
                order.order_id, chat_id, resp.text[:200],
            )
            return False
    except Exception as e:
        logger.exception("Error sending order status notification for %s: %s", order.order_id, e)
        return False


def send_excel_to_group(excel_file, submission):
    """
    Forward an uploaded Excel file to the Telegram group chat 2 (Instagram) using sendDocument.

    Returns True on success, False on failure.
    """
    if not BOT_TOKEN or not GROUP_CHAT_ID2:
        logger.error("Telegram not configured: BOT_TOKEN=%r, GROUP_CHAT_ID2=%r", BOT_TOKEN, GROUP_CHAT_ID2)
        return False

    # ── File size check ───────────────────────────────────────────────────────
    excel_file.seek(0, 2)
    file_size = excel_file.tell()
    excel_file.seek(0)

    if file_size > 50 * 1024 * 1024:
        logger.warning("Excel file too large (%d bytes) for submission %s", file_size, submission.pk)
        return False

    file_bytes = excel_file.read()
    file_name = getattr(excel_file, 'name', 'submission.xlsx')
    content_type = getattr(excel_file, 'content_type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    excel_file.seek(0)

    display_name = submission.telegram_username
    tg_id = ''
    if submission.user and hasattr(submission.user, 'telegram_profile'):
        profile = submission.user.telegram_profile
        display_name = profile.display_name
        tg_id = profile.telegram_id

    tg_line = f"\n🆔 *ID:* `{tg_id}`" if tg_id else ""

    caption = (
        f"📄 *Excel Submission*\n"
        f"👤 *User:* {_md(display_name)}{tg_line}\n"
        f"📋 *Session:* {_md(submission.session.title)}\n"
        f"📅 *Date:* {submission.target_date}\n"
        f"🔢 *IDs:* {submission.id_count}"
    )

    try:
        resp = _telegram_session.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendDocument',
            data={
                'chat_id': GROUP_CHAT_ID2,
                'caption': caption,
                'parse_mode': 'Markdown',
            },
            files={'document': (file_name, BytesIO(file_bytes), content_type)},
            timeout=(5, 60),
        )
    except requests.exceptions.ConnectionError as e:
        logger.error("Connection failed for excel submission %s: %s", submission.pk, e)
        return False
    except requests.exceptions.Timeout as e:
        logger.error("Timeout sending document for submission %s: %s", submission.pk, e)
        return False
    except Exception as e:
        logger.exception("Unexpected error sending document for submission %s: %s", submission.pk, e)
        return False

    if resp.status_code != 200:
        logger.error("sendDocument failed for submission %s: status=%d body=%s",
                     submission.pk, resp.status_code, resp.text[:300])
        return False

    logger.info("Excel document sent for submission %s", submission.pk)
    return True


def send_start_message(chat_id):
    """Send the /start welcome message with a Mini App button to a specific chat."""
    from telegram_auth.models import BotStartMessage

    config = BotStartMessage.load()
    keyboard = {
        'inline_keyboard': [[
            {
                'text': config.button_text,
             'web_app': {'url': 'https://jerinshop.onrender.com'},

            }
        ]]
    }

    payload = {
        'chat_id': chat_id,
        'text': _escape_mdv2(config.message_text),
        'reply_markup': keyboard,
        'parse_mode': 'MarkdownV2',
    }

    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    try:
        resp = _telegram_session.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.exception('Failed to send /start message — response: %s', resp.text)
        return {'ok': False, 'error': str(e), 'detail': resp.text}


def send_user_payment_report(chat_id, session_title, target_date, ok_count, rate, total, payments_summary):
    """Send a personal payment report to a user via Telegram."""
    payment_lines = '\n'.join(
        f"  {_md(method)}: `{_md(num)}`" for method, num in payments_summary
    ) if payments_summary else '  _No payment methods_'

    text = (
        f"📊 *Payment Report*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *Session:* {_md(session_title)}\n"
        f"📅 *Date:* {target_date}\n"
        f"\n"
        f"✅ *Approved IDs:* {ok_count}\n"
        f"💵 *Rate:* ৳{rate:.2f} per ID\n"
        f"💰 *Total Payment:* ৳{total:.2f}\n"
        f"\n"
        f"💳 *Payment Methods:*\n{payment_lines}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_Thank you for your work! 🎉_"
    )

    try:
        resp = _telegram_session.post(
            f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage',
            json={
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            logger.info("Payment report sent to chat_id %s", chat_id)
            return True
        else:
            logger.warning("sendUserPaymentReport failed for %s: %s", chat_id, resp.text[:200])
            return False
    except Exception as e:
        logger.exception("Error sending payment report to %s: %s", chat_id, e)
        return False