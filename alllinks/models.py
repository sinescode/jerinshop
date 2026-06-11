import re

from django.db import models


def extract_youtube_id(url):
    """Return YouTube video ID from a URL, or None."""
    if not url:
        return None
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


class APKLink(models.Model):
    app_name = models.CharField(max_length=200)
    apk_link = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'APK Link'
        verbose_name_plural = 'APK Links'

    def __str__(self):
        return self.app_name


class WorkMethod(models.Model):
    title = models.CharField(max_length=300)
    video_link = models.URLField(max_length=500)
    thumbnail_telegram_file_id = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Work Method'
        verbose_name_plural = 'Work Methods'

    @property
    def thumbnail_url(self):
        if self.thumbnail_telegram_file_id and self.pk:
            from django.urls import reverse
            return reverse('alllinks:thumbnail_proxy', args=[self.pk])
        video_id = extract_youtube_id(self.video_link)
        if video_id:
            return f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'
        return None

    def __str__(self):
        return self.title


class ChannelLink(models.Model):
    channel_name = models.CharField(max_length=200)
    link = models.URLField(max_length=500)
    icon_class = models.CharField(
        max_length=100, default='fab fa-telegram',
        help_text='Font Awesome 6 icon class, e.g. fab fa-telegram, fab fa-whatsapp, fab fa-youtube')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Channel Link'
        verbose_name_plural = 'Channel Links'

    def __str__(self):
        return self.channel_name


class SocialLink(models.Model):
    platform = models.CharField(max_length=100, help_text='e.g. Telegram, YouTube, Instagram')
    url = models.URLField(max_length=500)
    icon_class = models.CharField(
        max_length=100, default='fas fa-link',
        help_text='Font Awesome 6 icon class, e.g. fab fa-telegram, fab fa-youtube')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'pk']
        verbose_name = 'Social Link'
        verbose_name_plural = 'Social Links'

    def __str__(self):
        return self.platform


class TelegramRequiredConfig(models.Model):
    """Singleton — bot link shown on the 'Telegram Required' gate page."""
    bot_link = models.URLField(max_length=500, blank=True, default='https://t.me/')

    class Meta:
        verbose_name = 'Telegram Required Config'
        verbose_name_plural = 'Telegram Required Config'

    def __str__(self):
        return 'Telegram Required Config'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AboutUsConfig(models.Model):
    """Singleton — About Us page content with dynamic icon."""
    title = models.CharField(max_length=200, default='About Us')
    content = models.TextField(blank=True, default='')
    icon_class = models.CharField(
        max_length=100, default='fas fa-users',
        help_text='Font Awesome 6 icon class, e.g. fas fa-users, fas fa-info-circle')

    class Meta:
        verbose_name = 'About Us Config'
        verbose_name_plural = 'About Us Config'

    def __str__(self):
        return 'About Us Config'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'title': 'About Us', 'icon_class': 'fas fa-users'})
        return obj
