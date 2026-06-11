from django.conf import settings
from django.db import models
import random
import string


def generate_order_id():
    """Generate ID like MIH-A3X9K2"""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(random.choices(chars, k=10))
    return f"MIH-{suffix}"


class Coin(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, verbose_name="Display order")
    require_sender_token = models.BooleanField(
        default=False,
        verbose_name="Require sender username / coupon code",
        help_text="When ON, customers must provide a sender username or coupon code to place an order for this coin."
    )
    sender_token_label = models.CharField(
        max_length=100,
        default="Sender Username / Coupon Code",
        help_text="Label shown to the customer on the order form (e.g. 'Referral Code', 'Coupon Token')."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name

    def get_price_tiers(self):
        return self.price_tiers.order_by('min_amount')


class PriceTier(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name='price_tiers')
    min_amount = models.PositiveIntegerField(
        help_text="Minimum coin amount in raw coins (e.g., 1000 = 1K)"
    )
    max_amount = models.PositiveIntegerField(
        help_text="Maximum coin amount in raw coins (e.g., 5000 = 5K)"
    )
    price_per_k = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price per 1000 coins (1K)"
    )

    class Meta:
        ordering = ['min_amount']

    def __str__(self):
        return f"{self.coin.name}: {self.min_amount//1000}K-{self.max_amount//1000}K @ {self.price_per_k}/K"

    @property
    def min_k(self):
        return self.min_amount / 1000

    @min_k.setter
    def min_k(self, value):
        self.min_amount = int(float(value) * 1000)

    @property
    def max_k(self):
        return self.max_amount / 1000

    @max_k.setter
    def max_k(self, value):
        self.max_amount = int(float(value) * 1000)

    def display_range(self, use_k=True):
        if use_k:
            min_val = f"{self.min_k:.0f}K" if self.min_k == int(self.min_k) else f"{self.min_k}K"
            max_val = f"{self.max_k:.0f}K" if self.max_k == int(self.max_k) else f"{self.max_k}K"
            return f"{min_val} – {max_val}"
        return f"{self.min_amount} – {self.max_amount}"

    def display_range_k(self):
        return self.display_range(use_k=True)
    display_range_k.short_description = 'Range (K)'


class ReceiverAccount(models.Model):
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE, related_name='receiver_accounts')
    username = models.CharField(max_length=200)
    note = models.CharField(max_length=300, blank=True)

    def __str__(self):
        return f"{self.coin.name} → {self.username}"


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    order_id = models.CharField(
        max_length=20,
        unique=True,
        default=generate_order_id,
        editable=False,
        blank=True,
    )
    coin = models.ForeignKey(Coin, on_delete=models.PROTECT, related_name='orders')
    telegram_username = models.CharField(max_length=200)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
    )
    sender_token = models.CharField(
        max_length=200,
        blank=True,
        help_text="Sender username or coupon code submitted by the customer"
    )
    coin_amount = models.PositiveIntegerField(help_text="Amount in raw coins (e.g., 5000)")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    screenshot_telegram_file_id = models.CharField(max_length=500, blank=True)
    screenshot_url = models.URLField(blank=True)
    screenshot_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            models.Case(
                models.When(status='pending', then=0),
                default=1,
                output_field=models.IntegerField()
            ),
            'created_at'
        ]
        indexes = [
            models.Index(fields=['coin', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = generate_order_id()
        from django.db import IntegrityError
        while True:
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError:
                self.order_id = generate_order_id()

    def __str__(self):
        display = self.telegram_username
        if self.user and hasattr(self.user, 'telegram_profile'):
            display = self.user.telegram_profile.display_name
        return f"{self.order_id} - {display} - {self.coin_amount} {self.coin.name}"

    @property
    def coin_amount_k(self):
        return self.coin_amount / 1000


class OrderPayment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.ForeignKey('payments.GlobalPaymentMethod', on_delete=models.PROTECT)
    user_number = models.CharField(max_length=100, help_text="User's own account number")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_global = models.BooleanField(default=True)

    def __str__(self):
        return f"Order {self.order.order_id} → {self.payment_method.name}: {self.user_number}"
