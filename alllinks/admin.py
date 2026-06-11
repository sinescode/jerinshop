from io import BytesIO

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from unfold.admin import ModelAdmin

from coins.telegram_bot import _telegram_session
from .models import AboutUsConfig, APKLink, ChannelLink, SocialLink, TelegramRequiredConfig, WorkMethod


class WorkMethodForm(forms.ModelForm):
    thumbnail_file = forms.FileField(required=False, help_text='Upload a thumbnail image — it will be sent to Telegram.')
    clear_thumbnail = forms.BooleanField(required=False, label='Remove current thumbnail')

    class Meta:
        model = WorkMethod
        fields = '__all__'


@admin.register(APKLink)
class APKLinkAdmin(ModelAdmin):
    list_display = ('app_name', 'apk_link', 'created_at')
    search_fields = ('app_name',)


@admin.register(WorkMethod)
class WorkMethodAdmin(ModelAdmin):
    form = WorkMethodForm
    list_display = ('title', 'thumbnail_preview', 'video_link', 'created_at')
    search_fields = ('title',)
    readonly_fields = ('thumbnail_preview',)
    exclude = ('thumbnail_telegram_file_id',)

    def thumbnail_preview(self, obj):
        if obj.thumbnail_telegram_file_id and obj.pk:
            return format_html(
                '<img src="{}" style="max-height:60px;border-radius:8px;">',
                reverse('alllinks:thumbnail_proxy', args=[obj.pk]),
            )
        return '—'
    thumbnail_preview.short_description = 'Thumbnail'

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not obj or not obj.thumbnail_telegram_file_id:
            fields = [f for f in fields if f != 'clear_thumbnail']
        return fields

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get('clear_thumbnail'):
            obj.thumbnail_telegram_file_id = ''
            messages.success(request, 'Thumbnail removed.')
        thumbnail_file = form.cleaned_data.get('thumbnail_file')
        if thumbnail_file:
            file_id = self._upload_to_telegram(thumbnail_file, obj, request)
            if file_id:
                obj.thumbnail_telegram_file_id = file_id
        super().save_model(request, obj, form, change)

    def _upload_to_telegram(self, uploaded_file, obj, request):
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        chat_id = getattr(settings, 'TELEGRAM_GROUP_CHAT_ID', '')
        if not token or not chat_id:
            messages.warning(request, 'Telegram not configured — thumbnail not sent.')
            return None

        try:
            file_bytes = uploaded_file.read()
            file_name = uploaded_file.name or 'thumbnail.jpg'
            resp = _telegram_session.post(
                f'https://api.telegram.org/bot{token}/sendPhoto',
                data={
                    'chat_id': chat_id,
                    'caption': f'{obj.title}\n{obj.video_link}',
                },
                files={'photo': (file_name, BytesIO(file_bytes))},
                timeout=(5, 30),
            )
            if resp.status_code == 200:
                result = resp.json().get('result', {})
                photos = result.get('photo', [])
                file_id = photos[-1]['file_id'] if photos else ''
                if file_id:
                    messages.success(request, 'Thumbnail sent to Telegram group.')
                    return file_id
            messages.warning(request, f'Telegram send failed: HTTP {resp.status_code}')
        except Exception as e:
            messages.warning(request, f'Telegram send error: {e}')
        return None


@admin.register(ChannelLink)
class ChannelLinkAdmin(ModelAdmin):
    list_display = ('channel_name', 'link', 'icon_class', 'created_at')
    search_fields = ('channel_name', 'icon_class')


@admin.register(SocialLink)
class SocialLinkAdmin(ModelAdmin):
    list_display = ('platform', 'url', 'icon_class', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('platform', 'url')


@admin.register(TelegramRequiredConfig)
class TelegramRequiredConfigAdmin(ModelAdmin):
    list_display = ('__str__', 'bot_link')

    def has_add_permission(self, request):
        return not TelegramRequiredConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AboutUsConfig)
class AboutUsConfigAdmin(ModelAdmin):
    list_display = ('__str__', 'title', 'icon_class')

    def has_add_permission(self, request):
        return not AboutUsConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
