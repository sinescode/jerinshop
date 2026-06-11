# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jerin Shop — a Django 6.0.5 **Telegram Mini App (TWA)** that serves as a **coin marketplace**: users browse coin listings with per-method pricing tiers, place orders with payment screenshots, admins approve/reject via Telegram inline keyboards.

## Commands

```bash
# Run development server (SQLite)
# IMPORTANT: settings.py has DEBUG=False by default — flip to True for local dev
# or static files, media, and detailed error pages won't work.
python manage.py runserver

# Run with custom port
python manage.py runserver 0.0.0.0:8000

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser (for admin access)
python manage.py createsuperuser

# Collect static files (for production)
python manage.py collectstatic --noinput

# Access Django shell
python manage.py shell

# Production server (gunicorn on Render)
gunicorn jerinshop.wsgi --log-file -
```

> **Note on tests**: All `tests.py` files are stubs (3 lines each). There is no test suite — manual verification is the current norm.

## Architecture

### Apps and Their Roles

| App | Purpose | Key Models |
|-----|---------|------------|
| `telegram_auth` | Telegram Mini App login, user profiles, ban/suspension | `TelegramProfile` (1:1 with Django User), `BotStartMessage` (singleton) |
| `coins` | Coin marketplace: listings, orders, payments, Telegram bot | `Coin`, `PriceTier`, `Order`, `OrderPayment`, `ReceiverAccount` |
| `payments` | Payment method management (user-saved + global) | `GlobalPaymentMethod`, `UserPaymentMethod` |
| `home` | Landing page, Telegram-required gate, banned page | `HomeButton` |
| `alllinks` | Social links, work methods, APK links, About Us | `SocialLink`, `WorkMethod`, `APKLink`, `ChannelLink`, `TelegramRequiredConfig` (singleton), `AboutUsConfig` (singleton) |

### Authentication Flow

1. User opens the TWA in Telegram → client-side JS posts `initData` to `/api/auth/tg-login/`
2. Server verifies the HMAC-SHA256 signature using the bot token (`telegram_auth/auth_utils.py:verify_init_data`)
3. On success: creates or updates a Django User (username = `tg_{telegram_id}`, unusable password) and `TelegramProfile`; logs the user in; sets a `tg_web_token` in the session and a `tg_web_check` cookie
4. Client-side JS inside Telegram refreshes the `tg_web_check` cookie every 30 seconds
5. `TelegramCheckMiddleware` blocks requests that have a Django session but lack the matching `tg_web_check` cookie → prevents Chrome (which shares cookies with Android System WebView) from accessing the app outside Telegram
6. `BanCheckMiddleware` redirects banned/suspended users to `/banned/`; auto-clears expired suspensions

### Database

- **settings.py** defines PostgreSQL first (env vars: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, SSL required, 600s connection pooling), then **immediately overwrites it with SQLite** (`BASE_DIR / 'db.sqlite3'`). The second `DATABASES = {...}` block is the active one.
- **Production deployment**: The PostgreSQL config in `replacements.txt` is swapped into settings.py at deploy time (Render). The SQLite block is what you get running locally.
- `schema_patch.py` patches Django's SQLite schema editor for Turso compatibility (handles column mismatches in `INSERT INTO ... SELECT` during migrations) — imported as a side effect in settings

### Telegram Bot Integration (`coins/telegram_bot.py` + `coins/telegram_webhook.py`)

- Uses a persistent `requests.Session` with retry strategy (2 retries, 0.5s backoff)
- **Order flow**: User submits order → server sends photo + caption + inline keyboard (Approve/Reject) to `TELEGRAM_GROUP_CHAT_ID` via background thread
- **Webhook**: Receives callback queries at `/coins/telegram/webhook/` → parses `approve:ORDER_ID` or `reject:ORDER_ID` → updates order status → edits Telegram message caption/keyboard → sends personal notification to the user


- **`/start` command**: Replies with a configurable message + Mini App button (editable via `BotStartMessage` singleton in admin)
- MarkdownV2 escaping in `_escape_mdv2()` preserves intentional bold formatting and code blocks
- Screenshot deduplication via SHA-256 hash of uploaded files

### Middleware Stack

1. `TelegramCheckMiddleware` — validates `tg_web_check` cookie against session token for authenticated Telegram users; skips `/api/auth/tg-login/`, `/require-telegram/`, `/admin/`, `/static/`, `/media/`
2. `BanCheckMiddleware` — blocks banned/suspended users; auto-clears expired suspensions; skips same prefixes plus `/banned/`

### Payments API

The `payments` app exposes a REST-ish JSON API (all endpoints `@login_required`):

- `GET /payments/settings/` — settings page with all global methods + user's saved methods
- `GET /payments/api/methods/` — all global methods with user's saved account number per method
- `POST /payments/api/methods/save/` — create/update a single method (`global_method_id`, `account_number`)
- `POST /payments/api/methods/<id>/delete/` — delete a saved method
- `GET /payments/api/methods/list-grouped/` — saved methods grouped by `account_number` (for multi-select UI)
- `POST /payments/api/methods/batch-save/` — save one account number to multiple global methods at once; handles rename by deleting old-number rows when `old_account_number` differs
- `POST /payments/api/methods/batch-delete/` — delete all saved methods for a given account number
- `GET /payments/api/used-methods/` — global method IDs already used today in coin orders, used to disable already-used methods in the order form

### Frontend

- **Tailwind CSS v4** via `@tailwindcss/browser@4` CDN (`cdn.jsdelivr.net`), **Font Awesome 6** for icons, **Space Grotesk** (UI) and **Outfit** (headings) fonts
- Project-level error templates: `templates/400.html`, `403.html`, `404.html`, `500.html`, plus `admin/actions.html`
- Each app has its own `templates/<app>/` directory; admin override templates in `templates/admin/`
- `static/css/base.css` — custom styles

### Admin UI (django-unfold)

- All admin classes inherit from `unfold.admin.ModelAdmin`
- Uses `@display` decorator for list columns (with label color maps), `@action` decorator for bulk actions
- `OrderAdmin` uses a tabbed change list with separate paginators for pending/approved/cancelled statuses; displays a rich "order card" with copy-to-clipboard buttons
- `CoinAdmin` has an AJAX toggle button for `require_sender_token` + inline PriceTier and ReceiverAccount
- `TelegramProfileAdmin` and custom `UserAdmin` show rich activity cards and ban status badges
- `BotStartMessage`, `AboutUsConfig`, `TelegramRequiredConfig` are singletons (`pk=1`, `has_add_permission=False`)

### Key Design Decisions

- **Background thread for Telegram sends**: Caption is built in the main thread (safe DB access), then a daemon thread handles the network I/O to Telegram. The thread re-opens its own DB connection via `close_old_connections()` before writing `screenshot_telegram_file_id` back.
- **Payment method system**: `GlobalPaymentMethod` defines available methods; `UserPaymentMethod` stores per-user account numbers. Orders reference global methods through `OrderPayment`.
- **Screenshot proxy**: `/coins/order/<id>/screenshot/` and `/all-links/work-methods/<pk>/thumbnail/` both proxy Telegram file downloads through Django — avoids exposing the bot token to the client.
- **Excel parsing**: `openpyxl` in read-only mode; file data is copied to `BytesIO` before the workbook is closed (openpyxl's ZipFile wrapper closes the underlying handle).
- **Duplicate detection**: Coin orders use SHA-256 screenshot hashing — if the same screenshot is submitted twice, the duplicate order is rejected.

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token for Telegram API calls |
| `TELEGRAM_GROUP_CHAT_ID` | Group chat for coin order notifications |

| `TELEGRAM_WEBHOOK_SECRET` | Secret token to verify webhook requests from Telegram |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | PostgreSQL connection (production) |
| `ALLOWED_HOSTS` | Comma-separated host list |
| `TELEGRAM_PROXY` | Optional HTTP proxy for Telegram API calls |

### URL Structure

```
/admin/                                          # django-unfold admin
/api/auth/tg-login/                              # Telegram login (POST)
/api/auth/profile/                               # User profile page
/api/auth/history/                               # Combined order + submission history
/                                                # Home page (login required)
/require-telegram/                               # "Open in Telegram" gate page
/banned/                                         # Banned/suspended user page
/coins/                                          # Coin marketplace home
/coins/<id>/                                     # Coin detail with pricing tiers
/coins/<id>/order/                               # Order form
/coins/<id>/order/submit/                        # Order submission (POST)
/coins/order/<order_id>/success/                 # Order success page
/coins/order/<order_id>/screenshot/              # Screenshot proxy (via Telegram API)
/coins/search/                                   # Order search (GET ?order_id=)
/coins/api/calculate/                            # AJAX price calculation (GET)
/coins/telegram/webhook/                         # Telegram bot webhook (POST)
/payments/settings/                              # User payment method management
/payments/api/methods/                           # List methods with user's saved numbers
/payments/api/methods/save/                      # Save/update a method (POST)
/payments/api/methods/<id>/delete/               # Delete a method (POST)
/payments/api/methods/list-grouped/              # Grouped by account_number
/payments/api/methods/batch-save/                # Batch save/update (POST)
/payments/api/methods/batch-delete/              # Batch delete (POST)
/payments/api/used-methods/                      # Methods already used today

/all-links/                                      # Social links page
/all-links/work-methods/                         # Work method tutorials
/all-links/work-methods/<pk>/thumbnail/          # Thumbnail proxy (via Telegram API)
/all-links/apks/                                 # APK downloads
/all-links/channels/                             # Telegram channel links
/all-links/about-us/                             # About Us page
```

### Dependencies

- **Django 6.0.5** — web framework
- **django-unfold** — modern dark-themed admin interface
- **openpyxl** — Excel file parsing (submission uploads and report generation)
- **requests** + **urllib3** — Telegram Bot API HTTP calls with retry logic
- **gunicorn** — production WSGI server (Render deployment)
- **whitenoise** — static file serving in production
- **python-dotenv** — environment variable loading
- **psycopg2-binary** — PostgreSQL driver (production)

### Important Settings

- `LOGIN_URL = '/require-telegram/'` — unauthenticated users are redirected to the "Open in Telegram" gate, not a Django login form
- `SESSION_COOKIE_AGE = 604800` (7 days), `SESSION_SAVE_EVERY_REQUEST = True`
- `SESSION_COOKIE_SAMESITE = 'Lax'` — needed for cross-context cookie sharing between Telegram WebView and the server
- `CSRF_TRUSTED_ORIGINS` includes `*.ngrok-free.app` (dev tunneling), `*.onrender.com` (production), and the specific ngrok/resolve URLs
- `UNFOLD["STYLES"]` adds Font Awesome 6 CDN to the admin
- `Order.save()` has a retry loop: if `IntegrityError` is raised (duplicate `order_id`), it regenerates the random ID and retries
- `Order.Meta.ordering` uses a `Case`/`When` to sort pending orders first, then by date

### Time Zone

`Asia/Dhaka` (Bangladesh) — all datetimes are timezone-aware (`USE_TZ=True`).
