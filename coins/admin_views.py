from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from coins.models import Order
from coins.telegram_bot import send_order_status_notification

@staff_member_required
@require_POST
def order_quick_action(request, order_id):
    try:
        # order_id is now the string like MIH-XXXXXX, not pk
        order = Order.objects.get(order_id=order_id)
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'approve':
            order.status = Order.STATUS_APPROVED
        elif action == 'cancel':
            order.status = Order.STATUS_CANCELLED
        else:
            return JsonResponse({'ok': False, 'error': 'Unknown action'})

        order.save(update_fields=['status'])

        # Re-fetch with related data for notification
        fresh_order = Order.objects.filter(pk=order.pk).select_related(
            'user__telegram_profile', 'coin'
        ).first()
        if fresh_order:
            send_order_status_notification(fresh_order)

        return JsonResponse({'ok': True, 'new_status': order.status, 'order_id': order.order_id})
    except Order.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)