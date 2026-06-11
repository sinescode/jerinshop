from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('settings/', views.settings_page, name='settings'),
    path('api/methods/', views.api_list_methods, name='api_list_methods'),
    path('api/methods/save/', views.api_save_method, name='api_save_method'),
    path('api/methods/<int:method_id>/delete/', views.api_delete_method, name='api_delete_method'),
    path('api/methods/list-grouped/', views.api_list_grouped, name='api_list_grouped'),
    path('api/methods/batch-save/', views.api_batch_save, name='api_batch_save'),
    path('api/methods/batch-delete/', views.api_batch_delete, name='api_batch_delete'),
    path('api/used-methods/', views.api_used_methods, name='api_used_methods'),
]
