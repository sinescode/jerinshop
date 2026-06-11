from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin

from .models import BotStartMessage, TelegramProfile


@admin.register(TelegramProfile)
class TelegramProfileAdmin(admin.ModelAdmin):
    list_display = [
        'telegram_id',
        'display_name_col',
        'username_col',
        'ban_status_badge',
        'premium_badge',
        'order_count',
        'joined',
    ]
    list_display_links = ['display_name_col']
    search_fields = ['telegram_id', 'username', 'first_name', 'last_name']
    list_filter = ['is_banned', 'is_premium', 'created_at']
    readonly_fields = [
        'telegram_id', 'username', 'first_name', 'last_name',
        'language_code', 'is_premium', 'user_link',
        'ban_status_display', 'ban_reason_display', 'order_history',
        'created_at', 'updated_at',
    ]
    fieldsets = [
        ('Telegram Info', {
            'fields': [
                'telegram_id', 'username', 'first_name', 'last_name',
                'language_code', 'is_premium',
            ],
        }),
        ('Django User', {
            'fields': ['user_link'],
        }),
        ('Ban / Suspension', {
            'fields': [
                'ban_status_display', 'ban_reason_display',
            ],
        }),
        ('Activity', {
            'fields': ['order_history'],
        }),
        ('Timestamps', {
            'fields': ['created_at', 'updated_at'],
        }),
    ]
    actions = [
        'ban_users',
        'unban_users',
        'suspend_1h',
        'suspend_6h',
        'suspend_24h',
        'suspend_7d',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(
            _order_count=Count('user__orders', distinct=True),
            _submission_count=Count('user__submissions', distinct=True),
        )

    # ── List display ──────────────────────────────────────────────────────

    @admin.display(description='Name', ordering='first_name')
    def display_name_col(self, obj):
        return obj.display_name

    @admin.display(description='Username')
    def username_col(self, obj):
        if obj.username:
            return f'@{obj.username}'
        return '-'

    @admin.display(description='Ban', ordering='is_banned')
    def ban_status_badge(self, obj):
        if obj.is_permanently_banned:
            return format_html(
                '<span style="background:rgba(239,68,68,0.15);color:#f87171;'
                'border:1px solid rgba(239,68,68,0.3);padding:3px 10px;'
                'border-radius:100px;font-size:11px;font-weight:700;">{}</span>',
                'BANNED',
            )
        if obj.is_suspended:
            return format_html(
                '<span style="background:rgba(245,158,11,0.15);color:#fbbf24;'
                'border:1px solid rgba(245,158,11,0.3);padding:3px 10px;'
                'border-radius:100px;font-size:11px;font-weight:700;">{}</span>',
                'SUSPENDED',
            )
        return format_html(
            '<span style="background:rgba(0,230,138,0.12);color:#00e68a;'
            'border:1px solid rgba(0,230,138,0.3);padding:3px 10px;'
            'border-radius:100px;font-size:11px;font-weight:700;">{}</span>',
            'ACTIVE',
        )

    @admin.display(description='Premium', boolean=True)
    def premium_badge(self, obj):
        return obj.is_premium

    @admin.display(description='Orders', ordering='_order_count')
    def order_count(self, obj):
        count = getattr(obj, '_order_count', 0)
        if count:
            url = reverse('admin:coins_order_changelist') + f'?q={obj.telegram_id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return '0'

    @admin.display(description='Joined', ordering='created_at')
    def joined(self, obj):
        return obj.created_at.strftime('%b %d, %Y')

    # ── Detail fields ─────────────────────────────────────────────────────

    @admin.display(description='Django User')
    def user_link(self, obj):
        user = obj.user
        url = reverse('admin:auth_user_change', args=[user.pk])
        return format_html(
            '<a href="{}">{}</a> &middot; {}',
            url, user.username, user.email or 'no email',
        )

    @admin.display(description='Ban Status')
    def ban_status_display(self, obj):
        if not obj.is_banned:
            return format_html(
                '<span style="color:#00e68a;font-weight:600;">{}</span>',
                'Active',
            )
        if obj.is_permanently_banned:
            return format_html(
                '<span style="color:#f87171;font-weight:600;">{}</span>',
                'Permanently Banned',
            )
        if obj.is_suspended:
            remaining = obj.banned_until - timezone.now()
            hours = int(remaining.total_seconds() // 3600)
            mins = int((remaining.total_seconds() % 3600) // 60)
            return format_html(
                '<span style="color:#fbbf24;font-weight:600;">Suspended</span> '
                '<span style="color:#6b7a99;">&mdash; {}h {}m remaining</span>',
                hours, mins,
            )
        return format_html(
            '<span style="color:#6b7a99;">{}</span>',
            'Expired',
        )

    @admin.display(description='Reason')
    def ban_reason_display(self, obj):
        if not obj.is_banned:
            return '-'
        if obj.ban_reason:
            return obj.ban_reason
        return '-'

    @admin.display(description='Orders')
    def order_history(self, obj):
        from coins.models import Order
        orders = Order.objects.filter(user=obj.user).order_by('-created_at')[:10]
        if not orders:
            return 'No orders yet.'
        lines = []
        for o in orders:
            url = reverse('admin:coins_order_change', args=[o.pk])
            lines.append(format_html(
                '<a href="{}">#{}</a> {} — ৳{} <b>[{}]</b>',
                url, o.order_id, o.coin.name, o.total_amount, o.get_status_display(),
            ))
        return mark_safe('<br>'.join(lines))

    # ── Admin Actions ─────────────────────────────────────────────────────

    @admin.action(description='Ban selected users permanently')
    def ban_users(self, request, queryset):
        updated = queryset.update(
            is_banned=True,
            ban_reason='Banned by admin',
            banned_until=None,
            banned_at=timezone.now(),
        )
        self.message_user(request, f'{updated} user(s) banned permanently.')

    @admin.action(description='Unban selected users')
    def unban_users(self, request, queryset):
        updated = queryset.update(
            is_banned=False,
            ban_reason='',
            banned_until=None,
            banned_at=None,
        )
        self.message_user(request, f'{updated} user(s) unbanned.')

    @admin.action(description='Suspend for 1 hour')
    def suspend_1h(self, request, queryset):
        until = timezone.now() + timedelta(hours=1)
        updated = queryset.update(
            is_banned=True,
            ban_reason='Temporary suspension',
            banned_until=until,
            banned_at=timezone.now(),
        )
        self.message_user(request, f'{updated} user(s) suspended for 1 hour.')

    @admin.action(description='Suspend for 6 hours')
    def suspend_6h(self, request, queryset):
        until = timezone.now() + timedelta(hours=6)
        updated = queryset.update(
            is_banned=True,
            ban_reason='Temporary suspension',
            banned_until=until,
            banned_at=timezone.now(),
        )
        self.message_user(request, f'{updated} user(s) suspended for 6 hours.')

    @admin.action(description='Suspend for 24 hours')
    def suspend_24h(self, request, queryset):
        until = timezone.now() + timedelta(hours=24)
        updated = queryset.update(
            is_banned=True,
            ban_reason='Temporary suspension',
            banned_until=until,
            banned_at=timezone.now(),
        )
        self.message_user(request, f'{updated} user(s) suspended for 24 hours.')

    @admin.action(description='Suspend for 7 days')
    def suspend_7d(self, request, queryset):
        until = timezone.now() + timedelta(days=7)
        updated = queryset.update(
            is_banned=True,
            ban_reason='Temporary suspension',
            banned_until=until,
            banned_at=timezone.now(),
        )
        self.message_user(request, f'{updated} user(s) suspended for 7 days.')

    # ── Permissions ───────────────────────────────────────────────────────

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BotStartMessage)
class BotStartMessageAdmin(ModelAdmin):
    fieldsets = [
        ('Message', {'fields': ['message_text']}),
        ('Button', {
            'fields': ['button_text'],
            'description': 'This button will appear below the message and open the Mini App.',
        }),
    ]

    def has_add_permission(self, request):
        return False  # singleton — only one row via load()

    def has_delete_permission(self, request, obj=None):
        return False


# ── Custom User Admin (unfold-styled) ──────────────────────────────────

admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = [
        'username', 'email', 'first_name', 'last_name',
        'telegram_linked', 'ban_status_badge', 'is_active', 'date_joined',
    ]
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('telegram_profile')

    readonly_fields = [
        'telegram_info_card', 'ban_status_card', 'activity_card',
        'last_login', 'date_joined',
    ]

    fieldsets = [
        ('Account', {
            'fields': ['username', 'email', 'password'],
        }),
        ('Personal Info', {
            'fields': ['first_name', 'last_name'],
        }),
        ('Telegram Profile', {
            'fields': ['telegram_info_card'],
        }),
        ('Ban / Suspension', {
            'fields': ['ban_status_card'],
        }),
        ('Activity', {
            'fields': ['activity_card'],
        }),
        ('Permissions', {
            'fields': ['is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'],
        }),
        ('Important Dates', {
            'fields': ['last_login', 'date_joined'],
        }),
    ]

    # ── List display helpers ───────────────────────────────────────────

    @admin.display(description='Telegram', boolean=True)
    def telegram_linked(self, obj):
        return hasattr(obj, 'telegram_profile')

    @admin.display(description='Ban')
    def ban_status_badge(self, obj):
        profile = getattr(obj, 'telegram_profile', None)
        if not profile or not profile.is_banned:
            return format_html(
                '<span style="background:rgba(0,230,138,0.12);color:#00e68a;'
                'border:1px solid rgba(0,230,138,0.3);padding:3px 10px;'
                'border-radius:100px;font-size:11px;font-weight:700;">ACTIVE</span>',
            )
        if profile.is_permanently_banned:
            return format_html(
                '<span style="background:rgba(239,68,68,0.15);color:#f87171;'
                'border:1px solid rgba(239,68,68,0.3);padding:3px 10px;'
                'border-radius:100px;font-size:11px;font-weight:700;">BANNED</span>',
            )
        return format_html(
            '<span style="background:rgba(245,158,11,0.15);color:#fbbf24;'
            'border:1px solid rgba(245,158,11,0.3);padding:3px 10px;'
            'border-radius:100px;font-size:11px;font-weight:700;">SUSPENDED</span>',
        )

    # ── Change-form detail cards ───────────────────────────────────────

    @admin.display(description='Telegram Profile')
    def telegram_info_card(self, obj):
        profile = getattr(obj, 'telegram_profile', None)
        if not profile:
            url = reverse('admin:telegram_auth_telegramprofile_changelist')
            return format_html(
                '<div style="padding:16px;background:rgba(239,68,68,0.08);'
                'border:1px solid rgba(239,68,68,0.2);border-radius:12px;">'
                '<span style="color:#f87171;font-weight:600;">No Telegram profile linked.</span> '
                '<span style="color:#6b7a99;">The user must start the bot first.</span>'
                '</div>',
            )
        profile_url = reverse('admin:telegram_auth_telegramprofile_change', args=[profile.pk])
        return format_html(
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;'
            'padding:16px;background:rgba(99,102,241,0.06);'
            'border:1px solid rgba(99,102,241,0.2);border-radius:12px;">'
            '<div><span style="color:#6b7a99;font-size:11px;">TELEGRAM ID</span><br>'
            '<span style="font-weight:600;font-size:15px;">{tid}</span></div>'
            '<div><span style="color:#6b7a99;font-size:11px;">USERNAME</span><br>'
            '<span style="font-weight:600;font-size:15px;">@{uname}</span></div>'
            '<div><span style="color:#6b7a99;font-size:11px;">NAME</span><br>'
            '<span style="font-weight:600;font-size:15px;">{name}</span></div>'
            '<div><span style="color:#6b7a99;font-size:11px;">PREMIUM</span><br>'
            '<span style="font-weight:600;font-size:15px;">{prem}</span></div>'
            '<div style="grid-column:1/-1;margin-top:8px;">'
            '<a href="{url}" style="color:#818cf8;font-weight:600;text-decoration:none;">'
            'View Full Profile →</a></div>'
            '</div>',
            tid=profile.telegram_id,
            uname=profile.username or 'unknown',
            name=profile.display_name,
            prem='Yes' if profile.is_premium else 'No',
            url=profile_url,
        )

    @admin.display(description='Ban / Suspension Status')
    def ban_status_card(self, obj):
        profile = getattr(obj, 'telegram_profile', None)
        if not profile or not profile.is_banned:
            return format_html(
                '<div style="padding:16px;background:rgba(0,230,138,0.06);'
                'border:1px solid rgba(0,230,138,0.2);border-radius:12px;">'
                '<span style="color:#00e68a;font-weight:600;font-size:15px;">Active</span>'
                '<br><span style="color:#6b7a99;font-size:12px;">User is not banned or suspended.</span>'
                '</div>',
            )
        if profile.is_permanently_banned:
            reason = profile.ban_reason or 'No reason given'
            return format_html(
                '<div style="padding:16px;background:rgba(239,68,68,0.06);'
                'border:1px solid rgba(239,68,68,0.2);border-radius:12px;">'
                '<span style="color:#f87171;font-weight:600;font-size:15px;">Permanently Banned</span>'
                '<br><span style="color:#6b7a99;font-size:12px;">Reason: {}</span>'
                '</div>',
                reason,
            )
        remaining = profile.banned_until - timezone.now()
        hours = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)
        reason = profile.ban_reason or 'No reason given'
        return format_html(
            '<div style="padding:16px;background:rgba(245,158,11,0.06);'
            'border:1px solid rgba(245,158,11,0.2);border-radius:12px;">'
            '<span style="color:#fbbf24;font-weight:600;font-size:15px;">Suspended</span>'
            '<br><span style="color:#6b7a99;font-size:12px;">{}h {}m remaining &mdash; {}</span>'
            '</div>',
            hours, mins, reason,
        )

    @admin.display(description='Activity Overview')
    def activity_card(self, obj):
        from coins.models import Order
        order_count = Order.objects.filter(user=obj).count()
        order_url = reverse('admin:coins_order_changelist') + f'?q={obj.username}'
        return format_html(
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;'
            'padding:16px;background:rgba(99,102,241,0.04);'
            'border:1px solid rgba(99,102,241,0.15);border-radius:12px;">'
            '<div style="text-align:center;">'
            '<div style="font-size:28px;font-weight:800;color:#818cf8;">{orders}</div>'
            '<div style="color:#6b7a99;font-size:11px;">COIN ORDERS</div>'
            '<a href="{ourl}" style="color:#818cf8;font-size:11px;">View →</a></div>'
            '<div style="text-align:center;">'
            '<div style="font-size:28px;font-weight:800;color:#fbbf24;">{joined}</div>'
            '<div style="color:#6b7a99;font-size:11px;">JOINED</div></div>'
            '</div>',
            orders=order_count,
            joined=obj.date_joined.strftime('%b %d'),
            ourl=order_url,
        )
