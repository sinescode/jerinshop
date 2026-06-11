from .models import SocialLink, TelegramRequiredConfig


def social_links(request):
    links = SocialLink.objects.filter(is_active=True).order_by('order', 'pk')
    return {'social_links': links}


def telegram_required_config(request):
    return {'telegram_required_config': TelegramRequiredConfig.load()}
