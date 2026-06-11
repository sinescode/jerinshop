# Project Analysis: MetaIncomeHub

> Comprehensive analysis of the Django 6.0.5 project at `/home/kali/gitaction/paidproject/4metaincomehub`
>
> Generated: 2026-05-14

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Feature Inventory](#2-feature-inventory)
3. [Directory Structure](#3-directory-structure)
4. [Database Schema](#4-database-schema)
5. [URL Routing](#5-url-routing)
6. [Authentication Model](#6-authentication-model)
7. [API Endpoints](#7-api-endpoints)
8. [Frontend / UI](#8-frontend--ui)
9. [Configuration & Environment](#9-configuration--environment)
10. [Deployment](#10-deployment)
11. [Code Quality](#11-code-quality)
12. [Security Analysis](#12-security-analysis)
13. [Performance Considerations](#13-performance-considerations)
14. [Improvement Suggestions](#14-improvement-suggestions)
15. [Missing Features](#15-missing-features)

---

## 1. Project Overview

### 1.1 Purpose

MetaIncomeHub is a **Telegram Mini App (TWA)** -- a Django 6.0.5 web application that operates as a marketplace for buying/selling in-game currency ("coins") and as a platform for tracking Instagram social-media work submissions. Users authenticate via Telegram's Mini App init data (HMAC-SHA256 verified), browse coin listings, place orders with payment screenshots, and submit Instagram work (URLs). Administrators manage orders and submissions through a django-unfold themed admin interface with Telegram bot integration for real-time order notifications.

### 1.2 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0.5 (Python 3.13) |
| Database | SQLite (development), Turso/libSQL (production target) |
| Admin UI | django-unfold (dark-themed modern admin) |
| Frontend | Django Templates, Tailwind CSS (CDN), Font Awesome 6, Custom CSS |
| Fonts | Space Grotesk (UI), Outfit (display/headings) |
| Bot Integration | Telegram Bot API (HTTPS, retry session, inline keyboards) |
| Auth | Telegram Mini App init data verification (HMAC-SHA256) |
| Static Files | Whitenoise |
| File Processing | openpyxl (Excel parsing), BytesIO / base64 (image handling) |
| Deployment Target | Render.com |
| Tunneling | ngrok (development) |

### 1.3 Apps

| App | Purpose | Models |
|---|---|---|
| `home` | Landing page, About Us | `AboutUsConfig` (singleton) |
| `coins` | Coin marketplace: listings, pricing tiers, orders, payments | `Coin`, `PriceTier`, `ReceiverAccount`, `PaymentMethod`, `Order`, `OrderPayment` |
| `instagram_work` | Instagram submission tracking with session management | `SubmissionSession`, `SessionColumn`, `PricingTier`, `Submission`, `SubmissionPayment`, `SubmissionRow`, `ProcessedReport` |
| `telegram_auth` | Telegram authentication, user profiles, session management | `TelegramProfile`, `BotStartMessage` (singleton) |
| `alllinks` | Social links, Telegram required config (footer/menu data) | `SocialLink`, `TelegramRequiredConfig` (singleton) |

---

## 2. Feature Inventory

### 2.1 Authentication & User Management

| Feature | Implementation | Status |
|---|---|---|
| Telegram Mini App login | `tg_login` view -- form POST with initData, HMAC-SHA256 verification | Working |
| Session management | Django sessions, `tg_web_check` cookie middleware, 7-day expiry | Working |
| Ban/Suspension system | `TelegramProfile.is_banned`, `suspended_until` fields + `BanCheckMiddleware` | Working |
| Cookie guard middleware | `TelegramCheckMiddleware` -- validates `tg_web_check` cookie on every request | Working |
| Profile page | `/profile/` -- displays Telegram info, referral stats, ban status | Working |

### 2.2 Coin Marketplace

| Feature | Implementation | Status |
|---|---|---|
| Coin listing | `coins_home` view -- list all active coins with base price | Working |
| Coin detail / pricing tiers | `coin_detail` view -- shows coin info with per-method pricing | Working |
| Order form | `order_form` view -- coin + payment method selection, amount entry | Working |
| Price calculation | `calculate_price` (AJAX GET) -- returns total price for coin+method+amount | Working |
| Order submission | `submit_order` -- validates + creates order, generates order ID, captures screenshot | Working |
| Screenshot proxy | `screenshot_proxy` -- serves uploaded screenshots via authenticated proxy view | Working |
| Order search | `search_order` -- lookup order by custom ID | Working |
| Order history | `/history/` -- paginated list of user's orders and submissions | Working |
| Telegram notifications | `send_order_to_group` -- sends screenshot + details to Telegram group | Working |
| Approve/Reject actions | `telegram_webhook` -- inline keyboard callback handling | Working |

### 2.3 Instagram Work Submission

| Feature | Implementation | Status |
|---|---|---|
| Session-based submission | Weekly sessions with start/end times, max limits per session | Working |
| Excel file parsing | openpyxl -- reads number + method columns, validates rows | Working |
| Duplicate detection | Client-side SHA-256 hashing, rejected hashes stored in session | Working |
| Payment tracking | Per-submission payment records with method+number+value | Working |
| Pricing tiers | Amount-based pricing per Instagram method | Working |
| Admin report processing | Custom admin action -- computes earnings per user from submissions | Working |
| XLSX download | Custom admin view -- export submission data to Excel | Working |
| Session toggle | Admin can activate/deactivate sessions, toggle payment acceptance | Working |

### 2.4 Admin Interface

| Feature | Implementation | Status |
|---|---|---|
| django-unfold theming | Dark theme, Font Awesome icons, custom styles | Working |
| Coin admin | Custom change list with active toggle, order stats, bulk actions | Working |
| Order admin | Inline payments, custom card-based change list (tabbed: Pending/Approved/Rejected) | Working |
| Custom admin templates | `admin/coins/order/change_list.html` with card layout | Working |
| Instagram work admin | Date range filters, process report action, XLSX download | Working |
| About Us editor | Admin form for singleton AboutUsConfig | Working |
| Social link management | Admin CRUD for SocialLink model | Working |
| Bot start message editor | Admin form for BotStartMessage singleton | Working |

### 2.5 Telegram Bot Integration

| Feature | Implementation | Status |
|---|---|---|
| Order notification bot | Sends screenshot + structured message to group on new order | Working |
| Inline action buttons | Approve/Reject buttons on order messages | Working |
| Callback query handler | Webhook processes button clicks, updates order status | Working |
| Keyboard updates | Button state locks after action (shows "Approved"/"Rejected") | Working |
| /start welcome message | Sends configurable welcome with Mini App launch button | Working |
| Fallback on failure | Text-only fallback if image upload fails, size limits enforced | Working |

---

## 3. Directory Structure

```
4metaincomehub/
├── manage.py                          # Django management script
├── requirements.txt                   # Python dependencies (16 packages)
├── db.sqlite3                         # SQLite database (development)
├── .env                               # Environment variables (not in VCS)
│
├── metaincomehub/                     # Project configuration package
│   ├── __init__.py
│   ├── settings.py                    # Django settings (ALL config)
│   ├── urls.py                        # Root URL configuration
│   ├── wsgi.py                        # WSGI application
│   ├── asgi.py                        # ASGI application
│   ├── middleware.py                  # TelegramCheckMiddleware, BanCheckMiddleware
│   └── context_processors.py          # telegram_user context processor
│
├── home/                              # Landing page app
│   ├── __init__.py
│   ├── admin.py                       # AboutUsConfig admin registration
│   ├── models.py                      # AboutUsConfig (singleton)
│   ├── urls.py                        # URL patterns
│   ├── views.py                       # home, about_us views
│   └── templates/home/
│       ├── base.html                  # Base template (master layout)
│       ├── home.html                  # Landing page
│       └── about_us.html              # About Us page
│
├── coins/                             # Coin marketplace app
│   ├── __init__.py
│   ├── admin.py                       # CoinAdmin, OrderAdmin (custom)
│   ├── models.py                      # Coin, PriceTier, ReceiverAccount, PaymentMethod, Order, OrderPayment
│   ├── views.py                       # 7 views (marketplace + order workflow)
│   ├── urls.py                        # URL patterns
│   ├── telegram_bot.py                # Telegram notification functions
│   ├── telegram_webhook.py            # Telegram callback handler
│   ├── admin_urls.py                  # Custom admin URLs for coins
│   ├── filters.py                     # Custom admin filters (NullFieldListFilter, etc.)
│   └── templates/coins/
│       ├── coins_home.html            # Coin listing page
│       ├── coin_detail.html           # Coin detail with pricing
│       ├── order_form.html            # Order placement form
│       └── search_order.html          # Order search page
│   └── templates/admin/coins/
│       ├── order/
│       │   ├── change_list.html       # Card-based order list (tabbed)
│       │   └── change_form.html       # Order detail/edit form
│       └── app_index.html             # App index customization
│
├── instagram_work/                    # Instagram submission tracking app
│   ├── __init__.py
│   ├── admin.py                       # Custom admin views
│   ├── models.py                      # Session, Column, Pricing, Submission, Payment, Row, Report
│   ├── views.py                       # submission_home, get_used_methods, submit
│   ├── urls.py                        # URL patterns
│   ├── forms.py                       # SubmissionForm, NumberWithMethodsForm, BaseNumberFormSet
│   └── templates/instagram_work/
│       ├── submission_home.html       # Submission landing
│       └── submit.html               # Upload form
│   └── templates/admin/instagram_work/
│       └── submission/
│           └── change_list.html       # Custom change list with XLSX download button
│
├── telegram_auth/                     # Telegram auth app
│   ├── __init__.py
│   ├── admin.py                       # TelegramProfile admin, BotStartMessage admin
│   ├── models.py                      # TelegramProfile, BotStartMessage (singleton)
│   ├── views.py                       # tg_login, profile, history
│   ├── urls.py                        # URL patterns
│   ├── auth_utils.py                  # verify_init_data, get_or_create_telegram_user
│   └── templates/telegram_auth/
│       ├── login.html                 # Login page (Mini App init)
│       ├── profile.html               # User profile
│       └── history.html               # Order + submission history
│
├── alllinks/                          # Social links + config app
│   ├── __init__.py
│   ├── admin.py                       # SocialLink admin, TelegramRequiredConfig admin
│   ├── models.py                      # SocialLink, TelegramRequiredConfig (singleton)
│   ├── context_processors.py          # social_links, telegram_required_config
│   └── templates/alllinks/
│       └── links.html                 # Social links partial
│
├── static/                            # Static files (if any)
├── media/                             # User-uploaded media (screenshots, etc.)
├── staticfiles/                       # Collected static files (Whitenoise)
│
└── templates/                         # Project-level templates
    ├── 400.html                       # Bad request error page
    ├── 403.html                       # Permission denied error page
    ├── 404.html                       # Not found error page
    └── admin/
        └── actions.html               # Unfold admin actions template override
```

---

## 4. Database Schema

### 4.1 Entity Relationship Summary

```
SocialLink
     |
TelegramRequiredConfig (singleton, pk=1)
     |
AboutUsConfig (singleton, pk=1)
     |
BotStartMessage (singleton, pk=1)
     |
TelegramProfile --1:N-- Order --1:N-- OrderPayment
                             |             |
                             |       PaymentMethod
                             |
                          Coin --1:N-- PriceTier
                            |       --1:N-- ReceiverAccount
                            |
SubmissionSession --1:N-- Submission --1:N-- SubmissionPayment
      |                         |
      |                    SubmissionRow
      |
SessionColumn

PricingTier (instagram_work, independent)
ProcessedReport (independent)
```

### 4.2 Model Details

#### `home/models.py` -- `AboutUsConfig`

| Field | Type | Notes |
|---|---|---|
| pk | int (primary key) | Always 1 (singleton pattern) |
| content | TextField | About Us markdown content |
| updated_at | DateTimeField(auto_now) | |

#### `alllinks/models.py` -- `SocialLink`

| Field | Type | Notes |
|---|---|---|
| name | CharField(max_length=100) | Display name |
| url | URLField(max_length=500) | Link URL |
| icon | CharField(max_length=100) | Font Awesome icon class |
| order | IntegerField(default=0) | Display order |

#### `alllinks/models.py` -- `TelegramRequiredConfig`

| Field | Type | Notes |
|---|---|---|
| pk | int (primary key) | Always 1 (singleton pattern) |
| required_text | TextField | Message shown on non-Telegram access |
| updated_at | DateTimeField(auto_now) | |

#### `telegram_auth/models.py` -- `TelegramProfile`

| Field | Type | Notes |
|---|---|---|
| user | OneToOneField(User) | Django auth user |
| telegram_id | BigIntegerField(unique) | Telegram user ID |
| username | CharField(max_length=255, blank) | @username |
| first_name | CharField(max_length=255, blank) | |
| last_name | CharField(max_length=255, blank) | |
| photo_url | URLField(blank) | Telegram avatar URL |
| is_banned | BooleanField(default=False) | Ban flag |
| banned_at | DateTimeField(null) | When banned |
| suspended_until | DateTimeField(null) | Temp suspension expiry |
| suspension_reason | TextField(blank) | Reason for suspension |
| referral_code | CharField(unique, max_length=20) | Auto-generated |
| referred_by | ForeignKey('self', null) | Referrer |
| referral_count | IntegerField(default=0) | Denormalized count |
| created_at | DateTimeField(auto_now_add) | |
| updated_at | DateTimeField(auto_now) | |

#### `telegram_auth/models.py` -- `BotStartMessage`

| Field | Type | Notes |
|---|---|---|
| pk | int (primary key) | Always 1 (singleton pattern) |
| message_text | TextField | /start response text |
| button_text | CharField(max_length=100) | Mini App button label |
| updated_at | DateTimeField(auto_now) | |

#### `coins/models.py` -- `Coin`

| Field | Type | Notes |
|---|---|---|
| name | CharField(max_length=100) | Coin name |
| slug | SlugField(unique) | URL-friendly identifier |
| image | ImageField(upload_to='coins/') | Coin image |
| description | TextField(blank) | |
| base_price | DecimalField(max_digits=12, decimal_places=2) | Base price in BDT |
| is_active | BooleanField(default=True) | Listing active? |
| sender_token_label | CharField(max_length=50, null, blank) | Label for sender token field |
| order_count | IntegerField(default=0) | Denormalized total orders |
| success_count | IntegerField(default=0) | Denormalized approved orders |
| created_at | DateTimeField(auto_now_add) | |
| updated_at | DateTimeField(auto_now) | |

#### `coins/models.py` -- `PriceTier`

| Field | Type | Notes |
|---|---|---|
| coin | ForeignKey(Coin, CASCADE) | Parent coin |
| payment_method | ForeignKey(PaymentMethod) | Payment method this tier applies to |
| min_amount | IntegerField() | Min coins (inclusive) |
| max_amount | IntegerField() | Max coins (inclusive) |
| price_per_1k | DecimalField(max_digits=10, decimal_places=2) | Price per 1000 coins |
| is_active | BooleanField(default=True) | |

#### `coins/models.py` -- `ReceiverAccount`

| Field | Type | Notes |
|---|---|---|
| coin | ForeignKey(Coin, CASCADE) | Parent coin |
| payment_method | ForeignKey(PaymentMethod) | Payment method |
| account_label | CharField(max_length=200) | Display label |
| account_details | TextField() | Full account info |
| is_active | BooleanField(default=True) | |

#### `coins/models.py` -- `PaymentMethod`

| Field | Type | Notes |
|---|---|---|
| name | CharField(max_length=100) | Method name |
| slug | SlugField(unique) | URL identifier |
| description | TextField(blank) | |

#### `coins/models.py` -- `Order`

| Field | Type | Notes |
|---|---|---|
| order_id | CharField(primary_key, max_length=20) | Custom ID format: "MIH-XXXXX" |
| user | ForeignKey(User, SET_NULL, null) | Placed by |
| coin | ForeignKey(Coin, SET_NULL, null) | Coin purchased |
| coin_amount | IntegerField() | Amount of coins |
| total_amount | DecimalField(max_digits=12, decimal_places=2) | Total price in BDT |
| status | CharField(choices, default='pending') | pending/approved/rejected/cancelled |
| telegram_username | CharField(max_length=255, blank) | From Telegram profile |
| sender_token | CharField(max_length=500, blank) | Optional sender identifier |
| screenshot | ImageField(upload_to='screenshots/') | Payment proof |
| screenshot_hash | CharField(max_length=64, blank) | SHA-256 hash |
| telegram_message_id | IntegerField(null, blank) | For bot keyboard updates |
| admin_user | ForeignKey(User, SET_NULL, null, related_name='handled_orders') | Who approved/rejected |
| actioned_at | DateTimeField(null) | When status changed |
| created_at | DateTimeField(auto_now_add) | |
| updated_at | DateTimeField(auto_now) | |

#### `coins/models.py` -- `OrderPayment`

| Field | Type | Notes |
|---|---|---|
| order | ForeignKey(Order, CASCADE, related_name='payments') | Parent order |
| payment_method | ForeignKey(PaymentMethod) | Method used |
| user_number | CharField(max_length=50) | User's account number |
| created_at | DateTimeField(auto_now_add) | |

#### `instagram_work/models.py` -- `SubmissionSession`

| Field | Type | Notes |
|---|---|---|
| name | CharField(max_length=200) | Session name (e.g., "Week 12") |
| start_time | DateTimeField() | Session start |
| end_time | DateTimeField() | Session end |
| max_submissions | IntegerField(default=100) | Capacity |
| is_active | BooleanField(default=False) | Currently accepting? |
| payments_active | BooleanField(default=False) | Payments open? |
| created_at | DateTimeField(auto_now_add) | |

#### `instagram_work/models.py` -- `SessionColumn`

| Field | Type | Notes |
|---|---|---|
| session | ForeignKey(SubmissionSession, CASCADE) | Parent session |
| column_letter | CharField(max_length=5) | Excel column letter |
| method_name | CharField(max_length=200) | Display name |
| order | IntegerField(default=0) | Column order |

#### `instagram_work/models.py` -- `PricingTier`

| Field | Type | Notes |
|---|---|---|
| min_amount | IntegerField() | Min count (inclusive) |
| max_amount | IntegerField() | Max count (inclusive) |
| price_per_unit | DecimalField(max_digits=10, decimal_places=2) | Per-item price |
| is_active | BooleanField(default=True) | |

#### `instagram_work/models.py` -- `Submission`

| Field | Type | Notes |
|---|---|---|
| user | ForeignKey(User, CASCADE) | Submitted by |
| session | ForeignKey(SubmissionSession, SET_NULL, null) | Session |
| excel_file | FileField(upload_to='submissions/') | Uploaded Excel |
| total_amount | DecimalField(max_digits=10, decimal_places=2) | Calculated total |
| is_paid | BooleanField(default=False) | Payment received? |
| submission_count | IntegerField() | Number of items |
| created_at | DateTimeField(auto_now_add) | |

#### `instagram_work/models.py` -- `SubmissionPayment`

| Field | Type | Notes |
|---|---|---|
| submission | ForeignKey(Submission, CASCADE, related_name='payments') | |
| method_name | CharField(max_length=200) | Payment method name |
| user_number | CharField(max_length=50) | User's account number |
| value | IntegerField() | Number of submissions via this method |
| total_price | DecimalField(max_digits=10, decimal_places=2) | Calculated price |

#### `instagram_work/models.py` -- `SubmissionRow`

| Field | Type | Notes |
|---|---|---|
| submission | ForeignKey(Submission, CASCADE, related_name='rows') | |
| row_number | IntegerField() | Excel row |
| number_data | CharField(max_length=500) | Extracted number |
| method_name | CharField(max_length=200) | Assigned method |

#### `instagram_work/models.py` -- `ProcessedReport`

| Field | Type | Notes |
|---|---|---|
| session | ForeignKey(SubmissionSession, SET_NULL, null) | |
| user | ForeignKey(User, SET_NULL, null) | |
| total_submissions | IntegerField() | |
| total_earnings | DecimalField(max_digits=12, decimal_places=2) | |
| details | JSONField(default=dict) | Breakdown data |
| processed_at | DateTimeField(auto_now_add) | |

---

## 5. URL Routing

### 5.1 Root URLs (`metaincomehub/urls.py`)

| Path | Target | Name |
|---|---|---|
| `/` | `home.urls` | -- |
| `/coins/` | `coins.urls` | -- |
| `/instagram-work/` | `instagram_work.urls` | -- |
| `/auth/` | `telegram_auth.urls` | -- |
| `/admin/` | `admin.site.urls` | -- |
| `/telegram-webhook/` | `coins.telegram_webhook.webhook` | `telegram_webhook` |
| `/require-telegram/` | `telegram_auth.views.require_telegram` | `require_telegram` |
| `/screenshot/<path:path>` | `coins.views.screenshot_proxy` | `screenshot_proxy` |

Handler overrides: `handler400`, `handler403`, `handler404` pointing to custom error views.

### 5.2 Home URLs (`home/urls.py`)

| Path | View | Name |
|---|---|---|
| `/` | `home` | `home` |
| `/about-us/` | `about_us` | `about_us` |

### 5.3 Coins URLs (`coins/urls.py`)

| Path | View | Name |
|---|---|---|
| `/` | `coins_home` | `coins_home` |
| `/coin/<slug:coin_slug>/` | `coin_detail` | `coin_detail` |
| `/order/<slug:coin_slug>/` | `order_form` | `order_form` |
| `/submit-order/` | `submit_order` | `submit_order` |
| `/calculate-price/` | `calculate_price` | `calculate_price` |
| `/search-order/` | `search_order` | `search_order` |

### 5.4 Instagram Work URLs (`instagram_work/urls.py`)

| Path | View | Name |
|---|---|---|
| `/` | `submission_home` | `submission_home` |
| `/submit/` | `submit` | `submit` |
| `/get-used-methods/` | `get_used_methods` | `get_used_methods` |

### 5.5 Telegram Auth URLs (`telegram_auth/urls.py`)

| Path | View | Name |
|---|---|---|
| `/login/` | `tg_login` | `tg_login` |
| `/profile/` | `profile` | `profile` |
| `/history/` | `history` | `history` |

---

## 6. Authentication Model

### 6.1 Telegram Mini App Authentication Flow

1. **User opens Mini App in Telegram** -- Telegram injects `window.Telegram.WebApp` with user data
2. **initData generation** -- Telegram creates a signed query string: `query_id=...&auth_date=...&hash=...&user=...`
3. **Cookie handoff** -- The client sends `tg_web_check` cookie via `Telegram.WebApp.sendData()` or a dedicated handshake
4. **Server verification** -- `verify_init_data()` in `telegram_auth/auth_utils.py`:
   - Extracts `hash` from init data
   - Sorts remaining key-value pairs, joins with `\n`
   - Computes HMAC-SHA256 using `WebAppData` as key (derived from bot token)
   - Compares computed hash with received hash (constant-time comparison)
5. **User creation/login** -- `get_or_create_telegram_user()` fetches or creates Django `User` + `TelegramProfile`
6. **Session establishment** -- Standard Django session + `tg_web_check` cookie set
7. **Cookie guard** -- `TelegramCheckMiddleware` validates `tg_web_check` cookie on every request

### 6.2 Middleware Stack

**TelegramCheckMiddleware** (`metaincomehub/middleware.py`):
- Applied to all routes except: admin, login, webhook, require-telegram, static/media
- Checks `tg_web_check` cookie presence and validity
- Falls back to session-based check if cookie is absent but session is valid
- Returns 403 with custom template if unauthenticated

**BanCheckMiddleware** (`metaincomehub/middleware.py`):
- Runs after TelegramCheckMiddleware
- Checks `TelegramProfile.is_banned` and `suspended_until` for authenticated users
- Banned users: sets session message, redirects to home with alert
- Suspended users: shows remaining suspension time

### 6.3 Session Configuration

```
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 604800        # 7 days
SESSION_SAVE_EVERY_REQUEST = True
LOGIN_URL = '/require-telegram/'
```

### 6.4 Protection Layers

1. Telegram initData HMAC verification (server-side)
2. Cookie-based session guard (`tg_web_check`)
3. Ban/suspension enforcement
4. `@login_required` decorator on all sensitive views
5. Screenshot proxy requires authentication

---

## 7. API Endpoints

### 7.1 Internal AJAX Endpoints

| Method | Path | Purpose | Input | Output |
|---|---|---|---|---|
| GET | `/coins/calculate-price/` | Price calculation | `coin_id`, `payment_method_id`, `amount` | JSON `{total_price, price_per_1k}` |
| POST | `/coins/submit-order/` | Create order | FormData: coin, method, amount, screenshot, etc. | Redirect or JSON error |
| GET | `/instagram-work/get-used-methods/` | Used payment methods | Session ID | JSON `{used_methods: [...]}` |
| POST | `/instagram-work/submit/` | Submit Excel | FormData: file, session, payments | Redirect with messages |
| POST | `/auth/login/` | Telegram auth | Form POST with initData | Redirect or JSON `{ok, redirect}` |

### 7.2 External API

| Endpoint | Purpose | Method |
|---|---|---|
| Telegram Bot API `sendPhoto` | Send order screenshot to group | POST (outgoing) |
| Telegram Bot API `sendMessage` | Send order details / fallback messages | POST (outgoing) |
| Telegram Bot API `answerCallbackQuery` | Acknowledge inline button press | POST (outgoing) |
| Telegram Bot API `editMessageReplyMarkup` | Update keyboard after action | POST (outgoing) |
| Telegram Bot API `editMessageText` | Update message after action | POST (outgoing) |
| Telegram Bot API `getFile` | Resolve file_id to download URL | GET (outgoing) |
| Telegram Bot API webhook | Callback handler for bot actions | POST (incoming) |

### 7.3 Admin Custom Views

| Path | Purpose |
|---|---|
| `/admin/coins/order/<id>/change/` | Custom order change form with inline payments |
| `/admin/instagram_work/submission/download-xlsx/` | Export submissions as Excel |
| `/admin/instagram_work/submission/process-report/` | Compute earnings report |

---

## 8. Frontend / UI

### 8.1 Design System

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#0a0e17` | Primary background |
| `--card` | `#131827` | Card/surface background |
| `--card-hover` | `#1a2235` | Card hover state |
| `--fg` | `#e8edf5` | Primary text |
| `--muted` | `#8892a8` | Secondary/muted text |
| `--border` | `rgba(255,255,255,0.06)` | Subtle borders |
| `--accent` | `#00e68a` | Primary accent (green) |
| `--accent-dim` | `rgba(0,230,138,0.08)` | Dim accent background |
| `--danger` | `#ef4444` | Error/destructive actions |

### 8.2 Typography

| Font | Weight | Usage |
|---|---|---|
| Space Grotesk | 300-700 | Body text, UI elements, navigation |
| Outfit | 400-900 | Display text, headings, logo |

### 8.3 Template Architecture

- **Base template** (`home/base.html`): Single master layout with:
  - Responsive sidebar navigation (collapsible on mobile)
  - Dark theme with CSS custom properties
  - Tailwind CSS (CDN) + Font Awesome 6 + Google Fonts
  - Telegram WebApp integration (theme detection, back button, main button)
  - Cookie-based auth refresh (30-second interval for `tg_web_check`)
  - Loading overlay system with CSS animations
  - Django messages display
  - Footer with dynamic social links (from `SocialLink` model)
- **App templates**: Each app extends `base.html` with `{% block content %}`
- **Error templates**: Custom 400, 403, 404 pages with consistent styling
- **Admin templates**: django-unfold overrides for coins order list (card-based, tabbed)

### 8.4 Client-Side Features

| Feature | Implementation |
|---|---|
| Loading overlay | CSS keyframe animation with delayed display |
| Telegram theme sync | `window.Telegram.WebApp.colorScheme` detection |
| Auth cookie refresh | `setInterval` every 30s to refresh `tg_web_check` cookie |
| Mobile menu | Toggle sidebar via hamburger button |
| SHA-256 hashing | Client-side file hashing for duplicate detection |
| Dynamic payment methods | AJAX fetch of used methods in submission form |

---

## 9. Configuration & Environment

### 9.1 Environment Variables (`.env`)

| Variable | Purpose | Required |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token | Yes |
| `TELEGRAM_GROUP_CHAT_ID` | Group ID for order notifications | Yes |
| `TELEGRAM_WEBHOOK_SECRET` | Secret for webhook endpoint | Yes |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | Yes |
| `SECRET_KEY` | Django secret key | Falls back to hardcoded dev key |
| `DATABASE_URL` | Database connection URL | Planned but not used (SQLite fallback) |

### 9.2 Django Settings Highlights

- `DEBUG = False` -- production mode
- `CSRF_TRUSTED_ORIGINS` -- includes onrender.com and ngrok-free.app domains
- `TIME_ZONE = 'Asia/Dhaka'` -- Bangladesh timezone
- `USE_TZ = True` -- timezone-aware datetimes
- `STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'`

### 9.3 Dependencies (`requirements.txt`)

| Package | Version* | Purpose |
|---|---|---|
| Django | >=6.0.5,<6.1 | Web framework |
| django-unfold | >=0.5.4,<0.6.0 | Admin theming |
| whitenoise | >=6.9.0,<7.0 | Static file serving |
| python-dotenv | >=1.1.0,<2.0 | Environment loading |
| django-cors-headers | >=4.7.0,<5.0 | CORS support |
| openpyxl | >=3.1.5,<4.0 | Excel file processing |
| Pillow | >=11.1.0,<12.0 | Image handling |
| requests | >=2.32.3,<3.0 | HTTP client (Telegram API) |
| urllib3 | >=1.26,<3 | HTTP library dependency |
| gunicorn | >=23.0.0,<24.0 | WSGI server |
| psycopg2-binary | >=2.9.10,<3.0 | PostgreSQL adapter (future use) |
| django-cockroachdb | >=4.1.1,<5.0 | CockroachDB adapter |
| django-libsql-backend | >=0.1.0,<0.2.0 | Turso/libSQL backend |

\* Version specifiers as declared in requirements.txt

---

## 10. Deployment

### 10.1 Current Deployment

- **Platform**: Render.com (configured for Web Service)
- **WSGI**: gunicorn (production), Django dev server (development via ngrok)
- **Static Files**: Whitenoise with compressed manifest storage
- **Database**: SQLite (development); CockroachDB or Turso/libSQL targeted for production
- **Tunneling**: ngrok (`enhanced-mutt-gratefully.ngrok-free.app` -> localhost:8000)

### 10.2 Deployment Configuration

- `ALLOWED_HOSTS` configured via environment variable
- `CSRF_TRUSTED_ORIGINS` allows Render and ngrok domains
- Webhook URL for Telegram bot must be set to `https://<domain>/telegram-webhook/`

### 10.3 Deployment Notes

- The settings file has a hardcoded `SECRET_KEY` fallback -- production must override via environment
- SQLite is used for development; migrating to Turso/libSQL or CockroachDB requires config changes
- Static files are served via Whitenoise (no external CDN configured)
- No `start.sh` or `render.yaml` deployment manifest present in the repository

---

## 11. Code Quality

### 11.1 Strengths

- **Consistent patterns**: Singleton pattern used uniformly across 3 models (AboutUsConfig, BotStartMessage, TelegramRequiredConfig)
- **Good error handling**: Telegram bot functions have comprehensive try/except with logging
- **Retry strategy**: HTTP session with backoff retry for Telegram API calls
- **Denormalized counters**: `Coin.order_count` and `Coin.success_count` avoid expensive COUNT queries
- **Custom ID generation**: `generate_order_id()` with collision retry -- robust pattern
- **Auth separation**: Auth logic cleanly separated into `auth_utils.py`
- **Context processors**: Well-organized data injection (social links, Telegram config, user)
- **Custom admin filters**: NullFieldListFilter implemented for admin list filtering
- **Template organization**: Templates follow Django app template conventions

### 11.2 Issues

| Issue | Location | Severity | Description |
|---|---|---|---|
| Hardcoded SECRET_KEY | `settings.py:27` | HIGH | Fallback secret key exposed in source |
| SQLite in production | `settings.py:127-132` | MEDIUM | Not suitable for production scale |
| Some log messages may expose PII | Various logger calls | LOW | Error paths could leak user data |
| No database migrations | -- | MEDIUM | No migration files committed to repo |
| No test suite | -- | HIGH | Zero tests across the entire project |
| Commented CockroachDB credentials | `settings.py:112-126` | HIGH | Leftover production DB config exposed credentials |
| Inline styles in templates | Multiple HTML files | LOW | Mix of Tailwind classes and inline styles |
| Duplicate SESSION_SAVE_EVERY_REQUEST | `settings.py:137,139` | LOW | Setting declared twice |
| Sessions table growth | Middleware | MEDIUM | No session cleanup strategy for 7-day sessions |
| ngrok URL hardcoded | `coins/telegram_bot.py:330` | LOW | Mini App URL hardcoded to ngrok tunnel |

---

## 12. Security Analysis

### 12.1 Authentication & Authorization

| Layer | Assessment |
|---|---|
| Telegram initData verification | Strong -- HMAC-SHA256 with WebAppData derivation, constant-time comparison |
| Cookie guard middleware | Good -- validates tg_web_check on every request |
| Ban/suspension system | Good -- middleware enforcement, non-bypassable |
| `@login_required` usage | Good -- all sensitive views protected |
| Admin access | Django admin login (username/password) -- standard security model |

### 12.2 Data Protection

| Concern | Status |
|---|---|
| Screenshot access | Protected via `screenshot_proxy` view (auth required) |
| Telegram tokens | Loaded from environment variables |
| Payment info | Stored in plaintext in database (OrderPayment.user_number) |
| File uploads | Stored in `media/` directory, served via authenticated proxy |
| CSRF | Enabled globally, Trusted Origins whitelist configured |

### 12.3 Potential Risks

1. **Exposed SECRET_KEY**: The hardcoded fallback in `settings.py` is a Django-insecure dev key. If used in production, session forgery and cryptographic signing are compromised.

2. **Database credentials in comments**: The CockroachDB connection string (commented out) includes username, password, and host. If committed to public repo, this exposes cloud database credentials.

3. **Payment user numbers in plaintext**: `OrderPayment.user_number` stores user-provided account numbers without encryption. While not highly sensitive (typically phone numbers), this is PII with no protection at rest.

4. **File upload validation**: `submit_order` accepts screenshot uploads but has no explicit content-type validation or malware scanning beyond file size limits.

5. **Rate limiting absent**: No rate limiting on login attempts, order submissions, or file uploads.

6. **No HTTPS enforcement in app**: Relies on deployment platform for TLS termination.

### 12.4 Security Checklist

- [x] CSRF protection enabled
- [x] Session security (SameSite=Lax, 7-day expiry)
- [x] Custom error pages (no stack traces leaked)
- [x] Environment variable based secrets
- [x] Authentication on all sensitive views
- [ ] No test suite
- [ ] No rate limiting
- [ ] No input content validation for uploads
- [ ] Payment data stored in plaintext
- [ ] No audit logging for admin actions

---

## 13. Performance Considerations

### 13.1 Current Bottlenecks

| Area | Issue | Impact |
|---|---|---|
| Database | SQLite single-writer -- no concurrent writes | Low for current scale |
| Queries | Denormalized counters mitigate COUNT queries | Good |
| File uploads | Screenshots stored on application server | Scales poorly |
| Telegram API | Sequential bot message sends (photo then text) | Low latency |
| Excel parsing | openpyxl loads entire workbook into memory | Fine for current file sizes |
| Static files | Whitenoise serving -- no CDN | Fine for low traffic |
| Asset loading | Tailwind CSS + Font Awesome from CDN | Latency dependent on CDN |

### 13.2 Optimization Opportunities

1. **Database migration to Turso/CockroachDB**: Enables horizontal scaling and concurrent writes
2. **Object storage for uploads**: Move screenshots/submissions to S3-compatible storage
3. **Query optimization**: Some views may benefit from `select_related` / `prefetch_related` (not verified)
4. **Static file CDN**: Configure CloudFront or similar for static assets
5. **Redis caching**: For pricing tier lookups and frequently accessed configuration

---

## 14. Improvement Suggestions

### 14.1 Critical (Security)

1. **Remove hardcoded SECRET_KEY** -- Move entirely to environment variable, fail hard if not set
2. **Remove commented credentials** -- Strip the CockroachDB connection string with credentials
3. **Add rate limiting** -- Use django-ratelimit or middleware-based approach on auth and submission endpoints
4. **Encrypt payment data** -- At minimum, user_number in OrderPayment and SubmissionPayment

### 14.2 High Priority

5. **Add test suite** -- Critical for a production application handling payments:
   - Unit tests for auth verification
   - Integration tests for order workflow
   - Telegram bot interaction tests
6. **Add database migrations** -- Initialize and version database schema
7. **Environment-based settings** -- Use `django-environ` or similar for clean env management
8. **Structured logging** -- Add request IDs, consistent log format, log levels

### 14.3 Medium Priority

9. **Object storage for uploads** -- Move screenshots and Excel files to S3/DO Spaces
10. **Admin audit log** -- Track who approved/rejected orders and processed submissions
11. **Webhook security** -- Validate Telegram webhook secret token on incoming requests
12. **Improve error pages** -- 500 error page is missing (only 400, 403, 404 exist)
13. **Add CI/CD** -- GitHub Actions for lint, test, deploy pipeline
14. **User notification** -- Notify users when their order is approved/rejected via Telegram DM

### 14.4 Low Priority

15. **Refactor templates** -- Extract repeated error page CSS into shared stylesheet
16. **Screenshot compression** -- Compress screenshots before upload to save bandwidth
17. **Email/password auth alternative** -- For non-Telegram admin access
18. **i18n support** -- Add locale infrastructure for future Bangla/English toggle
19. **Accessibility audit** -- Add ARIA labels, keyboard navigation improvements

---

## 15. Missing Features

### 15.1 Functional Gaps

| Feature | Why Needed | Complexity |
|---|---|---|
| User-facing order status notifications | Users must manually check order status | Low |
| Withdrawal/wallet system | Users earn from submissions but can't withdraw | High |
| Admin dashboard with charts | No analytics on orders, revenue, user growth | Medium |
| Email/notification preferences | Users can't configure how they're notified | Low |
| Multi-language support | Bangladesh market (Bengali + English) | Medium |
| Payment gateway integration | Manual payment verification (screenshots) is labor-intensive | High |
| Order cancellation by user | Users cannot cancel their own orders | Low |
| Submission review workflow | Submissions lack a review/quality-check step | Medium |
| Referral rewards system | Referral tracking exists but no reward mechanism | Medium |

### 15.2 Technical Gaps

| Feature | Why Needed | Complexity |
|---|---|---|
| Automated database backups | No backup strategy for SQLite production | Low |
| Health check endpoint | No `/health/` or `/ready/` endpoints for deployment platform | Low |
| Containerization | No Dockerfile for reproducible deployment | Medium |
| Monitoring/alerting | No error tracking (Sentry), no uptime monitoring | Low |
| API documentation | No OpenAPI/Swagger for internal AJAX endpoints | Low |
| Database migration framework | Migration files absent -- schema changes require manual sync | Low |
| Load testing | No performance baseline or capacity plan | Medium |

### 15.3 Telegram Bot Gaps

| Feature | Why Needed | Complexity |
|---|---|---|
| DM notifications to user | User gets no notification when order is approved/rejected | Low |
| Broadcast messaging | Admin cannot send announcements to all users | Low |
| Order status command | Users can't check order status via bot | Low |
| Automatic webhook setup | Currently must manually configure webhook URL | Low |

---

## Appendix A: Data Flow Diagrams

### A.1 Order Placement Flow

```
User -> Order Form -> POST /coins/submit-order/
  |
  +-- Validate form data
  +-- Generate Order ID (MIH-XXXXX)
  +-- SHA-256 hash screenshot
  +-- Save Order + OrderPayment records
  +-- Debit coin stock (order_count++)
  |
  +-- Send to Telegram Group:
      +-- Send screenshot with caption
      +-- Send full details with Approve/Reject keyboard
           as reply to screenshot message
```

### A.2 Order Approval Flow

```
Admin clicks "Approve" in Telegram group
  |
  +-- Telegram API sends POST to /telegram-webhook/
  +-- Verify webhook secret
  +-- Parse callback_data: approve:<order_id>
  +-- Update Order status to 'approved'
  +-- Increment Coin.success_count
  +-- Update Telegram message:
  |   +-- Edit text to show "Approved" status
  |   +-- Lock Approve button, keep Reject active
  +-- Answer callback query
```

### A.3 Instagram Submission Flow

```
User -> Submission Form -> POST /instagram-work/submit/
  |
  +-- Check session active + capacity
  +-- Parse Excel via openpyxl
  +-- Client-side SHA-256 hash check (duplicate detection)
  +-- Validate row count against session limits
  +-- Calculate pricing via PricingTier
  +-- Validate payment methods
  +-- Create Submission + SubmissionPayment + SubmissionRow records
  +-- Store rejected hashes in session
```

---

## Appendix B: Key Code Patterns

### B.1 Singleton Model Pattern

```python
class SingletonModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

Used by: `AboutUsConfig`, `BotStartMessage`, `TelegramRequiredConfig`

### B.2 Order ID Generation

```python
def generate_order_id():
    """Format: MIH-XXXXX (5 alphanumeric chars, ~36M combinations)"""
    while True:
        order_id = 'MIH-' + ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=5))
        if not Order.objects.filter(order_id=order_id).exists():
            return order_id
```

### B.3 Telegram Session with Retry

```python
_telegram_session = requests.Session()
_retry_strategy = Retry(
    total=2, backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["POST", "GET"],
)
_adapter = HTTPAdapter(max_retries=_retry_strategy)
_telegram_session.mount("https://", _adapter)
```

---

## Appendix C: Admin Customization Summary

| App | Model | Customizations |
|---|---|---|
| coins | Coin | Active toggle, order stats columns, bulk set active/inactive actions |
| coins | Order | Inline OrderPayment, custom change_list (card-based, tabbed Pending/Approved/Rejected), custom change_form, approve/cancel admin actions |
| instagram_work | Submission | Custom change_list with "Download XLSX" button + date form, "Process Report" admin action, toggle is_paid action, toggle session action |
| telegram_auth | TelegramProfile | Ban/suspension fields in change form |
| telegram_auth | BotStartMessage | Singleton admin |
| home | AboutUsConfig | Singleton admin |
| alllinks | SocialLink | Standard admin |
| alllinks | TelegramRequiredConfig | Singleton admin |

---

*End of Project Analysis*
