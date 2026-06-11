from django.urls import path

from . import views

app_name = 'telegram_auth'

urlpatterns = [
    path('tg-login/', views.tg_login, name='tg_login'),
    path('profile/', views.profile, name='profile'),
    path('history/', views.history, name='history'),
]
