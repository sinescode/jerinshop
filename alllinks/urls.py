from django.urls import path

from . import views

app_name = 'alllinks'

urlpatterns = [
    path('', views.all_links, name='home'),
    path('work-methods/', views.work_methods, name='work_methods'),
    path('work-methods/<int:pk>/thumbnail/', views.thumbnail_proxy, name='thumbnail_proxy'),
    path('apks/', views.apk_links, name='apk_links'),
    path('channels/', views.channel_links, name='channel_links'),
    path('about-us/', views.about_us, name='about_us'),
]
