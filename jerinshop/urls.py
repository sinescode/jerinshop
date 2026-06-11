from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from coins.admin_views import order_quick_action

urlpatterns = [
    path('admin/coins/order/<str:order_id>/quick-action/', order_quick_action, name='order_quick_action'),

    path('admin/', admin.site.urls),
    path('api/auth/', include('telegram_auth.urls')),
    path('', include('home.urls')),

    path('coins/', include('coins.urls', namespace='coins')),
    path('payments/', include('payments.urls')),
    path('all-links/', include('alllinks.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Required for Django to use your 400.html template
handler400 = 'django.views.defaults.bad_request'
handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'