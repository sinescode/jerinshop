from django.conf import settings
from django.db import models


class GlobalPaymentMethod(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True,
        help_text="Optional description shown to users")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Global Payment Method"
        verbose_name_plural = "Global Payment Methods"

    def __str__(self):
        return self.name


class UserPaymentMethod(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_payment_methods',
    )
    global_method = models.ForeignKey(
        GlobalPaymentMethod,
        on_delete=models.CASCADE,
        related_name='user_methods',
    )
    account_number = models.CharField(
        max_length=100,
        help_text="User's account/phone number for this method",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="User can toggle this on/off without deleting",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('user', 'global_method')]
        ordering = ['global_method__name']
        verbose_name = "User Payment Method"
        verbose_name_plural = "User Payment Methods"

    def __str__(self):
        return f"{self.user} - {self.global_method.name}: {self.account_number}"

    @property
    def display_name(self):
        return self.global_method.name

    @property
    def is_global(self):
        return True
