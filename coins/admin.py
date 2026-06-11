from django.contrib import admin
from django import forms
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.utils.html import format_html, escape, escapejs
from django.urls import reverse, path
from django.utils.safestring import mark_safe
from django.http import JsonResponse

from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display, action

from .models import Coin, PriceTier, ReceiverAccount, Order, OrderPayment


# ─── Price Tiers ──────────────────────────────────────────────────────────────

class PriceTierForm(forms.ModelForm):
    min_k = forms.DecimalField(
        label='Min (K)', min_value=0,
        help_text='e.g. 1 for 1,000 coins', decimal_places=2
    )
    max_k = forms.DecimalField(
        label='Max (K)', min_value=0,
        help_text='e.g. 5 for 5,000 coins', decimal_places=2
    )

    class Meta:
        model = PriceTier
        fields = ('min_k', 'max_k', 'price_per_k')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['min_k'].initial = self.instance.min_amount / 1000
            self.fields['max_k'].initial = self.instance.max_amount / 1000

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.min_amount = int(self.cleaned_data['min_k'] * 1000)
        instance.max_amount = int(self.cleaned_data['max_k'] * 1000)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class PriceTierInline(TabularInline):
    model = PriceTier
    form = PriceTierForm
    extra = 1
    fields = ('min_k', 'max_k', 'price_per_k')
    tab = True  # Unfold: render inline inside a tab


class ReceiverAccountInline(TabularInline):
    model = ReceiverAccount
    extra = 1
    fields = ('username', 'note')
    tab = True  # Unfold: render inline inside a tab


# ─── Coin ─────────────────────────────────────────────────────────────────────

@admin.register(Coin)
class CoinAdmin(ModelAdmin):
    list_display = (
        'order', 'name', 'is_active', 'sender_token_status',
        'created_at', 'pending_orders', 'approved_orders', 'cancelled_orders'
    )
    list_display_links = ('name',)
    list_editable = ('is_active', 'order')

    # Unfold: use fieldsets with collapsible / tab support
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'is_active'),
        }),
        ('Sender Username / Coupon Code', {
            'fields': ('require_sender_token', 'sender_token_label'),
            'description': (
                'Turn this ON to require customers to enter a sender username or coupon code '
                'when placing an order for this coin. You can customise the label shown to them.'
            ),
            'classes': ['tab'],  # Unfold: collapsible section
        }),
    )

    inlines = [PriceTierInline, ReceiverAccountInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _pending_count=Count('orders', filter=Q(orders__status='pending')),
            _approved_count=Count('orders', filter=Q(orders__status='approved')),
            _cancelled_count=Count('orders', filter=Q(orders__status='cancelled')),
        )

    # Unfold: bulk actions use the @action decorator
    actions = ['delete_approved_orders', 'delete_cancelled_orders']
    actions_list = ['delete_approved_orders', 'delete_cancelled_orders']

    # ── Custom URL for AJAX toggle ────────────────────────────────────────────
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/toggle-sender-token/',
                self.admin_site.admin_view(self.toggle_sender_token_view),
                name='coins_coin_toggle_sender_token',
            ),
        ]
        return custom + urls

    def toggle_sender_token_view(self, request, pk):
        if request.method != 'POST':
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(['POST'])
        try:
            coin = Coin.objects.get(pk=pk)
        except Coin.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        coin.require_sender_token = not coin.require_sender_token
        coin.save(update_fields=['require_sender_token'])
        return JsonResponse({
            'ok': True,
            'value': coin.require_sender_token,
            'label': coin.sender_token_label or 'Sender Token',
        })

    # ── Column renderers (Unfold @display decorator) ──────────────────────────

    @display(description='Sender / Coupon')
    def sender_token_status(self, obj):
        toggle_url = reverse('admin:coins_coin_toggle_sender_token', args=[obj.pk])
        if obj.require_sender_token:
            btn_style = (
                'background:#7c3aed;color:#fff;border:none;padding:3px 12px;'
                'border-radius:10px;font-size:11px;font-weight:600;cursor:pointer;'
                'transition:opacity .15s;'
            )
            btn_text = f'ON — {obj.sender_token_label or "Sender Token"}'
        else:
            btn_style = (
                'background:#374151;color:#9ca3af;border:none;padding:3px 12px;'
                'border-radius:10px;font-size:11px;font-weight:600;cursor:pointer;'
                'transition:opacity .15s;'
            )
            btn_text = 'OFF'

        return format_html(
            '''<button
                data-toggle-url="{url}"
                data-label="{label}"
                onclick="(function(btn){{
                    var csrfToken = document.cookie.match(/csrftoken=([^;]+)/);
                    csrfToken = csrfToken ? csrfToken[1] : '';
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                    fetch(btn.dataset.toggleUrl, {{
                        method: 'POST',
                        headers: {{'X-CSRFToken': csrfToken}},
                    }})
                    .then(function(r){{ return r.json(); }})
                    .then(function(d){{
                        if (d.ok) {{
                            if (d.value) {{
                                btn.style.background = '#7c3aed';
                                btn.style.color = '#fff';
                                btn.textContent = 'ON — ' + d.label;
                            }} else {{
                                btn.style.background = '#374151';
                                btn.style.color = '#9ca3af';
                                btn.textContent = 'OFF';
                            }}
                        }}
                        btn.disabled = false;
                        btn.style.opacity = '1';
                    }})
                    .catch(function(){{
                        btn.disabled = false;
                        btn.style.opacity = '1';
                    }});
                }})(this)"
                style="{style}"
            >{text}</button>''',
            url=toggle_url,
            label=obj.sender_token_label or 'Sender Token',
            style=btn_style,
            text=btn_text,
        )

    def _order_link(self, obj, status, label, color, count):
        url = reverse('admin:coins_order_changelist') + f'?coin__id__exact={obj.pk}&status__exact={status}'
        return mark_safe(
            f'<a href="{url}" style="background:{color};color:#fff;padding:2px 9px;'
            f'border-radius:10px;font-size:11px;font-weight:600;text-decoration:none;">'
            f'{label} {count}</a>'
        )

    @display(description='Pending')
    def pending_orders(self, obj):
        return self._order_link(obj, 'pending', '<i class="fas fa-hourglass-half"></i>', '#f59e0b', getattr(obj, '_pending_count', 0))

    @display(description='Approved')
    def approved_orders(self, obj):
        return self._order_link(obj, 'approved', '<i class="fas fa-check-circle"></i>', '#10b981', getattr(obj, '_approved_count', 0))

    @display(description='Cancelled')
    def cancelled_orders(self, obj):
        return self._order_link(obj, 'cancelled', '<i class="fas fa-circle-xmark"></i>', '#ef4444', getattr(obj, '_cancelled_count', 0))

    # ── Bulk actions (Unfold @action decorator) ───────────────────────────────

    @action(description='🗑️ Delete all APPROVED orders for selected coins')
    def delete_approved_orders(self, request, queryset=None):
        if queryset is None:
            queryset = self.get_queryset(request)
        coin_ids = list(queryset.values_list('pk', flat=True))
        deleted, _ = Order.objects.filter(coin_id__in=coin_ids, status='approved').delete()
        self.message_user(request, f"Deleted {deleted} approved orders across {len(coin_ids)} coins.")
        return redirect('admin:coins_coin_changelist')

    @action(description='🗑️ Delete all CANCELLED orders for selected coins')
    def delete_cancelled_orders(self, request, queryset=None):
        if queryset is None:
            queryset = self.get_queryset(request)
        coin_ids = list(queryset.values_list('pk', flat=True))
        deleted, _ = Order.objects.filter(coin_id__in=coin_ids, status='cancelled').delete()
        self.message_user(request, f"Deleted {deleted} cancelled orders across {len(coin_ids)} coins.")
        return redirect('admin:coins_coin_changelist')


# ─── Order ────────────────────────────────────────────────────────────────────

class OrderPaymentInline(TabularInline):
    model = OrderPayment
    extra = 0
    readonly_fields = ('payment_method', 'user_number', 'amount')
    tab = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = (
        'order_id', 'status_badge', 'telegram_username',
        'sender_token_display', 'coin', 'coin_amount_k', 'total_amount', 'created_at'
    )
    list_filter = ('status', 'coin')
    search_fields = ('telegram_username', 'order_id', 'sender_token')
    readonly_fields = (
        'order_id', 'coin', 'telegram_username', 'sender_token',
        'coin_amount_k', 'total_amount',
        'created_at', 'updated_at', 'order_card_display'
    )
    inlines = [OrderPaymentInline]
    change_list_template = 'admin/coins/order/change_list.html'
    change_form_template = 'admin/coins/order/change_form.html'

    # Unfold: list actions use @action decorator
    actions = ['approve_orders', 'cancel_orders']
    actions_list = ['approve_orders', 'cancel_orders']

    @display(description='Amount (K)', ordering='coin_amount')
    def coin_amount_k(self, obj):
        return f"{obj.coin_amount / 1000:.2f}K"

    @display(description='Sender / Token')
    def sender_token_display(self, obj):
        if obj.sender_token:
            return format_html(
                '<code style="background:#ede9fe;color:#6d28d9;padding:2px 8px;'
                'border-radius:6px;font-size:12px;">{}</code>',
                obj.sender_token
            )
        return mark_safe('<span style="color:#d1d5db;font-size:12px;">—</span>')

    list_per_page = 10

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'coin', 'user__telegram_profile'
        ).prefetch_related(
            'payments__payment_method'
        ).order_by('-created_at')

    @display(description='Status', ordering='status', label={
        'pending': 'warning',
        'approved': 'success',
        'cancelled': 'danger',
    })
    def status_badge(self, obj):
        # Unfold natively supports label colors via the label dict above.
        # The method still returns the display value for the label to render.
        return obj.get_status_display()

    @display(description='Order Card')
    def order_card_display(self, obj):
        # ── Pre-escape user-controlled values ──────────────────────────────────
        h_order_id = escape(obj.order_id)
        if obj.user and hasattr(obj.user, 'telegram_profile'):
            h_username = escape(obj.user.telegram_profile.display_name)
        else:
            h_username = escape(obj.telegram_username)
        h_coin_name = escape(obj.coin.name)
        h_amount_str = escape(f"{obj.total_amount:.2f}")
        # JS string context (clipboard writes)
        js_order_id = escapejs(obj.order_id)
        js_amount_str = escapejs(f"{obj.total_amount:.2f}")

        # ── Payments ───────────────────────────────────────────────────────────
        payments_html = ''
        for p in obj.payments.all():
            method = escape(p.payment_method.name)
            num = escape(p.user_number)
            js_num = escapejs(p.user_number)
            payments_html += (
                f'<div style="margin:6px 0;display:flex;align-items:center;gap:10px;">'
                f'<span style="font-weight:600;color:#6b7280">{method}:</span>'
                f'<code style="background:#f3f4f6;padding:4px 10px;border-radius:6px;'
                f'font-size:14px;letter-spacing:1px">{num}</code>'
                f'<button onclick="navigator.clipboard.writeText(\'{js_num}\');'
                f'this.textContent=\'Copied!\';'
                f'setTimeout(()=>this.textContent=\'Copy\',1500)"'
                f' style="background:#3b82f6;color:#fff;border:none;padding:4px 10px;'
                f'border-radius:6px;cursor:pointer;font-size:12px">Copy</button>'
                f'</div>'
            )

        # ── Screenshot ─────────────────────────────────────────────────────────
        screenshot_html = ''
        if obj.screenshot_url:
            screenshot_html = (
                f'<img src="{escape(obj.screenshot_url)}" '
                f'style="max-width:320px;border-radius:10px;border:2px solid #e5e7eb;margin-bottom:12px;" />'
            )
        elif obj.screenshot_telegram_file_id:
            screenshot_html = '<p style="color:#6b7280;font-style:italic">Screenshot in Telegram</p>'

        coin_amount_k = obj.coin_amount / 1000
        amount_display = f"{coin_amount_k:.2f}K" if coin_amount_k % 1 != 0 else f"{coin_amount_k:.0f}K"

        # ── Sender / coupon token ──────────────────────────────────────────────
        sender_token_html = ''
        if obj.sender_token:
            token = escape(obj.sender_token)
            js_token = escapejs(obj.sender_token)
            token_label = escape(obj.coin.sender_token_label if obj.coin_id else "Sender / Token")
            sender_token_html = (
                f'<div style="margin-bottom:10px;">'
                f'<span style="font-weight:700;color:#111">{token_label}:</span>'
                f'<code style="background:#ede9fe;padding:3px 10px;border-radius:6px;'
                f'font-size:13px;font-weight:700;letter-spacing:1px;color:#6d28d9">{token}</code>'
                f'<button onclick="navigator.clipboard.writeText(\'{js_token}\');'
                f'this.textContent=\'Copied!\';'
                f'setTimeout(()=>this.textContent=\'Copy\',1500)"'
                f' style="background:#7c3aed;color:#fff;border:none;padding:3px 10px;'
                f'border-radius:6px;cursor:pointer;font-size:12px;">Copy</button>'
                f'</div>'
            )

        # ── Main card ──────────────────────────────────────────────────────────
        html = (
            f'<div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:14px;'
            f'padding:22px;max-width:480px;box-shadow:0 2px 8px rgba(0,0,0,0.07);">'
            f'{screenshot_html}'
            f'<div style="margin-bottom:10px;">'
            f'<span style="font-weight:700;color:#111">Order ID:</span>'
            f'<code style="background:#f3f4f6;padding:3px 10px;border-radius:6px;'
            f'font-size:13px;font-weight:700;letter-spacing:1px;">{h_order_id}</code>'
            f'<button onclick="navigator.clipboard.writeText(\'{js_order_id}\');'
            f'this.textContent=\'Copied!\';'
            f'setTimeout(()=>this.textContent=\'Copy\',1500)"'
            f' style="background:#6b7280;color:#fff;border:none;padding:3px 10px;'
            f'border-radius:6px;cursor:pointer;font-size:12px;">Copy</button>'
            f'</div>'
            f'<div style="margin-bottom:10px">'
            f'<span style="font-weight:700;color:#111">Telegram:</span>'
            f'<span style="color:#3b82f6">{h_username}</span>'
            f'</div>'
            f'{sender_token_html}'
            f'<div style="margin-bottom:10px">'
            f'<span style="font-weight:700;color:#111">Coin:</span> {h_coin_name}'
            f'</div>'
            f'<div style="margin-bottom:10px">'
            f'<span style="font-weight:700;color:#111">Coin Amount:</span> {amount_display}'
            f'</div>'
            f'<div style="margin-bottom:6px;font-weight:700;color:#111">Payout Numbers:</div>'
            f'{payments_html}'
            f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid #e5e7eb;'
            f'display:flex;align-items:center;gap:10px;">'
            f'<span style="font-weight:700;color:#111;font-size:16px">Total to Pay:</span>'
            f'<code style="background:#fef3c7;padding:6px 14px;border-radius:8px;'
            f'font-size:18px;font-weight:700;color:#92400e">{h_amount_str}</code>'
            f'<button onclick="navigator.clipboard.writeText(\'{js_amount_str}\');'
            f'this.textContent=\'Copied!\';'
            f'setTimeout(()=>this.textContent=\'Copy\',1500)"'
            f' style="background:#f59e0b;color:#fff;border:none;padding:6px 14px;'
            f'border-radius:8px;cursor:pointer;font-weight:600">Copy</button>'
            f'</div>'
            f'</div>'
        )
        return mark_safe(html)

    def get_fields(self, request, obj=None):
        if obj:
            return ('order_card_display', 'status', 'updated_at')
        return ('coin', 'telegram_username', 'coin_amount', 'total_amount', 'status')

    @action(description='✅ Mark selected as Approved')
    def approve_orders(self, request, queryset=None):
        if queryset is None:
            queryset = self.get_queryset(request).filter(status='pending')

        # Capture PKs before bulk update so we can re-fetch for notifications
        order_pks = list(queryset.values_list('pk', flat=True))
        count = queryset.update(status='approved')
        self.message_user(request, f"{count} orders marked as approved.")

        if order_pks:
            from .telegram_bot import send_order_status_notification
            for order in Order.objects.filter(
                pk__in=order_pks
            ).select_related('user__telegram_profile', 'coin'):
                send_order_status_notification(order)

        return redirect('admin:coins_order_changelist')

    @action(description='❌ Mark selected as Cancelled')
    def cancel_orders(self, request, queryset=None):
        if queryset is None:
            queryset = self.get_queryset(request).filter(status='pending')

        # Capture PKs before bulk update so we can re-fetch for notifications
        order_pks = list(queryset.values_list('pk', flat=True))
        count = queryset.update(status='cancelled')
        self.message_user(request, f"{count} orders marked as cancelled.")

        if order_pks:
            from .telegram_bot import send_order_status_notification
            for order in Order.objects.filter(
                pk__in=order_pks
            ).select_related('user__telegram_profile', 'coin'):
                send_order_status_notification(order)

        return redirect('admin:coins_order_changelist')

    def save_model(self, request, obj, form, change):
        """
        Detect status changes on the change form and notify the user.
        """
        old_status = None
        if change and obj.pk:
            try:
                old_status = Order.objects.get(pk=obj.pk).status
            except Order.DoesNotExist:
                pass

        super().save_model(request, obj, form, change)

        # Send notification if status was changed to a terminal state
        if change and old_status != obj.status and obj.status in ('approved', 'cancelled'):
            # Re-fetch with related data for the notification helper
            fresh_order = Order.objects.filter(pk=obj.pk).select_related(
                'user__telegram_profile', 'coin'
            ).first()
            if fresh_order:
                from .telegram_bot import send_order_status_notification
                send_order_status_notification(fresh_order)

    def changelist_view(self, request, extra_context=None):
        from django.core.paginator import Paginator
        qs = self.get_queryset(request)

        per_page = self.list_per_page
        extra_context = extra_context or {}
        extra_context['pending_page'] = Paginator(qs.filter(status='pending'), per_page).get_page(
            request.GET.get('pending_page', 1))
        extra_context['approved_page'] = Paginator(qs.filter(status='approved'), per_page).get_page(
            request.GET.get('approved_page', 1))
        extra_context['cancelled_page'] = Paginator(qs.filter(status='cancelled'), per_page).get_page(
            request.GET.get('cancelled_page', 1))
        return super().changelist_view(request, extra_context=extra_context)
