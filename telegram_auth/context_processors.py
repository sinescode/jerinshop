def telegram_user(request):
    """Make Telegram user info available to all templates."""
    result = {
        'telegram_user': None,
        'is_telegram_authenticated': False,
        'tg_web_token': '',
    }
    if request.user.is_authenticated and hasattr(request.user, 'telegram_profile'):
        profile = request.user.telegram_profile
        result['telegram_user'] = profile
        result['is_telegram_authenticated'] = True
        result['tg_web_token'] = request.session.get('tg_web_token', '')
    return result
