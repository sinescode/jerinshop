import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.conf import settings
from django.contrib.auth.models import User

from .models import TelegramProfile


def verify_init_data(init_data: str) -> dict | None:
    """
    Verify Telegram Mini App initData string.
    Returns the user dict on success, None on failure.
    """
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        return None

    try:
        parsed = dict(parse_qsl(init_data))
        received_hash = parsed.pop('hash', None)
        if not received_hash:
            return None

        items = sorted(parsed.items())
        data_check_string = '\n'.join(f"{k}={v}" for k, v in items)

        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode('utf-8'),
            hashlib.sha256
        ).digest()

        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_hash, received_hash):
            return None

        auth_date = int(parsed.get('auth_date', 0))
        if time.time() - auth_date > 86400:
            return None

        user_data = json.loads(parsed.get('user', '{}'))
        return user_data

    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def get_or_create_telegram_user(telegram_user_data: dict) -> tuple[User, bool]:
    """Get or create a Django User + TelegramProfile from Telegram user data."""
    telegram_id = telegram_user_data['id']
    username = telegram_user_data.get('username', '')
    first_name = telegram_user_data.get('first_name', '')
    last_name = telegram_user_data.get('last_name', '')
    language_code = telegram_user_data.get('language_code', '')
    is_premium = telegram_user_data.get('is_premium', False)

    try:
        profile = TelegramProfile.objects.select_related('user').get(telegram_id=telegram_id)
        changed = False
        for field, value in [
            ('username', username),
            ('first_name', first_name),
            ('last_name', last_name),
            ('language_code', language_code),
            ('is_premium', is_premium),
        ]:
            if getattr(profile, field) != value:
                setattr(profile, field, value)
                changed = True
        if changed:
            profile.save(update_fields=[
                'username', 'first_name', 'last_name',
                'language_code', 'is_premium', 'updated_at',
            ])
        return profile.user, False
    except TelegramProfile.DoesNotExist:
        pass

    user = User.objects.create_user(
        username=f"tg_{telegram_id}",
        first_name=first_name,
        last_name=last_name,
    )
    user.set_unusable_password()
    user.save()

    TelegramProfile.objects.create(
        user=user,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
        is_premium=is_premium,
    )
    return user, True
