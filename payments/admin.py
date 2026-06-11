from django.contrib import admin
from django.db.models import Count
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import GlobalPaymentMethod, UserPaymentMethod


@admin.register(GlobalPaymentMethod)
class GlobalPaymentMethodAdmin(ModelAdmin):
    list_display = ('name', 'is_active', 'user_count', 'created_at')
    list_editable = ('is_active',)
    search_fields = ('name',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _user_count=Count('user_methods', distinct=True)
        )

    @display(description='Users')
    def user_count(self, obj):
        return getattr(obj, '_user_count', 0)


@admin.register(UserPaymentMethod)
class UserPaymentMethodAdmin(ModelAdmin):
    list_display = ('user', 'display_name', 'account_number', 'type_badge', 'is_active', 'created_at')
    list_filter = ('is_active', 'global_method')
    search_fields = ('user__username', 'account_number', 'custom_name')
    list_editable = ('is_active',)

    @display(description='Type')
    def type_badge(self, obj):
        return 'Global' if obj.is_global else 'Custom'
