from django.urls import path
from home.views import home, require_telegram, banned

urlpatterns = [
    path('', home, name='home'),
    path('require-telegram/', require_telegram, name='require_telegram'),
    path('banned/', banned, name='banned'),
]