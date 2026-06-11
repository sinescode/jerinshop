from django.urls import path
from . import views
from .telegram_webhook import telegram_webhook

app_name = 'coins'

urlpatterns = [
    path('', views.coins_home, name='home'),
    path('<int:coin_id>/', views.coin_detail, name='coin_detail'),
    path('<int:coin_id>/order/', views.order_form, name='order_form'),
    path('<int:coin_id>/order/submit/', views.submit_order, name='submit_order'),
    path('order/<str:order_id>/success/', views.order_success, name='order_success'),
    # AJAX
    path('api/calculate/', views.calculate_price, name='calculate_price'),
    path('search/', views.search_order, name='search_order'),
    path('order/<str:order_id>/screenshot/', views.screenshot_proxy, name='screenshot_proxy'),
    path('telegram/webhook/', telegram_webhook, name='telegram_webhook'),
]
