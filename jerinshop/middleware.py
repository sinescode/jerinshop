import logging

from django.shortcuts import redirect
from django.utils import timezone

logger = logging.getLogger(__name__)


class TelegramCheckMiddleware:
    """Blocks authenticated requests that lack a valid ``tg_web_check`` cookie.

    On Android the Telegram Mini App uses System WebView, which shares its
    cookie store with Chrome.  This means a Django session cookie set inside
    Telegram can be sent by Chrome too.

    The mitigation works as follows:

    * During ``/api/auth/tg-login/`` a random token is stored in the session
      (``tg_web_token``) and returned to the client both as a JSON field and
      as a ``tg_web_check`` cookie.
    * Client-side JavaScript that **only runs inside the Telegram WebView**
      periodically refreshes the ``tg_web_check`` cookie (every 30 s) so it
      never expires.
    * This middleware checks, for every authenticated request that has a
      ``telegram_profile``, that the cookie matches the session token.  If it
      does not (cookie expired, missing, or wrong) the request is redirected
      to ``/require-telegram/``.

    Chrome cannot keep the cookie alive because the Telegram WebView JS never
    executes there.  After at most 60 s the cookie expires and the middleware
    starts blocking.
    """

    SKIP_PREFIXES = (
        '/api/auth/tg-login/',
        '/require-telegram/',
        '/admin/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Allow whitelisted paths through unconditionally.
        if path.startswith(self.SKIP_PREFIXES):
            return self.get_response(request)

        # Only enforce the check for authenticated Telegram users.
        if not (request.user.is_authenticated
                and hasattr(request.user, 'telegram_profile')):
            return self.get_response(request)

        session_token = request.session.get('tg_web_token')
        cookie_token = request.COOKIES.get('tg_web_check')

        if session_token and cookie_token and session_token == cookie_token:
            # All good — the request is coming from inside Telegram.
            return self.get_response(request)

        # Block — this request is almost certainly from a browser.
        logger.warning(
            'TelegramCheckMiddleware blocked request from user %s '
            '(path: %s, has_session_token: %s, has_cookie_token: %s)',
            request.user.pk, path,
            bool(session_token), bool(cookie_token),
        )

        response = redirect('/require-telegram/')
        response.delete_cookie('tg_web_check', path='/', samesite='Lax')
        return response


class BanCheckMiddleware:
    """Blocks banned or suspended Telegram users from accessing the site.

    * Permanently banned users are redirected to a banned page immediately.
    * Temporarily suspended users are blocked until their suspension expires.
    * Expired suspensions are auto-cleared (is_banned set back to False).
    """

    SKIP_PREFIXES = (
        '/api/auth/tg-login/',
        '/require-telegram/',
        '/banned/',
        '/admin/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        if path.startswith(self.SKIP_PREFIXES):
            return self.get_response(request)

        if not (request.user.is_authenticated
                and hasattr(request.user, 'telegram_profile')):
            return self.get_response(request)

        profile = request.user.telegram_profile

        # Auto-clear expired suspensions
        if profile.is_banned and profile.banned_until and profile.banned_until <= timezone.now():
            profile.is_banned = False
            profile.banned_until = None
            profile.save(update_fields=['is_banned', 'banned_until'])
            return self.get_response(request)

        if profile.is_banned:
            logger.info(
                'BanCheckMiddleware blocked user %s (telegram_id=%s, reason=%s)',
                request.user.pk, profile.telegram_id, profile.ban_reason,
            )
            return redirect('/banned/')

        return self.get_response(request)
