from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class TelegramProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='telegram_profile',
    )
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, blank=True, default='')
    first_name = models.CharField(max_length=255, blank=True, default='')
    last_name = models.CharField(max_length=255, blank=True, default='')
    language_code = models.CharField(max_length=10, blank=True, default='')
    is_premium = models.BooleanField(default=False)

    # Ban / suspension
    is_banned = models.BooleanField(default=False, db_index=True)
    ban_reason = models.TextField(blank=True, default='')
    banned_until = models.DateTimeField(null=True, blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        if self.username:
            return f"@{self.username}"
        if self.first_name:
            return self.first_name
        return f"tg:{self.telegram_id}"

    @property
    def is_suspended(self):
        """Temporary suspension that hasn't expired yet."""
        return self.is_banned and self.banned_until and self.banned_until > timezone.now()

    @property
    def is_permanently_banned(self):
        """Permanent ban (is_banned=True, no expiry)."""
        return self.is_banned and self.banned_until is None

    @property
    def ban_status_display(self):
        if not self.is_banned:
            return 'Active'
        if self.is_permanently_banned:
            return 'Banned'
        if self.is_suspended:
            return f'Suspended until {self.banned_until.strftime("%b %d, %Y %H:%M")}'
        return 'Expired'


class BotStartMessage(models.Model):
    """Singleton model — stores the /start welcome message editable from admin."""
    message_text = models.TextField(
        default='Welcome to Jerin Shop! 🚀\n\nEarn money by completing simple tasks and submitting your work.',
        help_text='Message shown when a user sends /start to the bot (Markdown supported).',
    )
    button_text = models.CharField(
        max_length=100,
        default='Open Jerin Shop',
        help_text='Label for the button that opens the Mini App.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Bot Start Message'
        verbose_name_plural = 'Bot Start Message'

    def save(self, *args, **kwargs):
        # Ensure singleton — always save to pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return 'Bot /start Message'
