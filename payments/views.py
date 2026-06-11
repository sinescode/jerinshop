import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from coins.models import Order

from .models import GlobalPaymentMethod, UserPaymentMethod


@login_required
@ensure_csrf_cookie
def settings_page(request):
    """Render the Payment Settings page for the Mini App."""
    global_methods = GlobalPaymentMethod.objects.filter(is_active=True)
    saved_methods = UserPaymentMethod.objects.filter(
        user=request.user
    ).select_related('global_method')

    # Group saved methods by account_number for the multi-select UI
    grouped = {}
    for sm in saved_methods:
        grouped.setdefault(sm.account_number, []).append(sm.global_method_id)

    return render(request, 'payments/settings.html', {
        'global_methods': global_methods,
        'saved_methods': saved_methods,
        'saved_grouped_json': json.dumps([
            {'account_number': num, 'global_method_ids': ids}
            for num, ids in grouped.items()
        ]),
        'global_json': json.dumps([
            {'id': gm.pk, 'name': gm.name}
            for gm in global_methods
        ]),
    })


@login_required
def api_list_methods(request):
    """Return all global methods with user's saved numbers."""
    global_methods = GlobalPaymentMethod.objects.filter(is_active=True)
    saved = UserPaymentMethod.objects.filter(
        user=request.user
    ).select_related('global_method')

    saved_by_global = {s.global_method_id: s for s in saved}

    result = []
    for gm in global_methods:
        user_method = saved_by_global.get(gm.pk)
        result.append({
            'id': gm.pk,
            'name': gm.name,
            'user_account_number': user_method.account_number if user_method else None,
            'user_method_id': user_method.pk if user_method else None,
            'is_saved_and_active': user_method.is_active if user_method else False,
        })

    return JsonResponse({'methods': result})


@login_required
@require_POST
def api_save_method(request):
    """Save or update a user's payment method."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    global_method_id = data.get('global_method_id')
    account_number = data.get('account_number', '').strip()
    is_active = data.get('is_active', True)

    if not account_number:
        return JsonResponse({'error': 'Account number is required'}, status=400)

    if not global_method_id:
        return JsonResponse({'error': 'A payment method is required'}, status=400)

    global_method = get_object_or_404(GlobalPaymentMethod, pk=global_method_id, is_active=True)
    method, created = UserPaymentMethod.objects.update_or_create(
        user=request.user,
        global_method=global_method,
        defaults={
            'account_number': account_number,
            'is_active': is_active,
        }
    )

    return JsonResponse({
        'ok': True,
        'id': method.pk,
        'created': created,
        'display_name': method.display_name,
    })


@login_required
@require_POST
def api_delete_method(request, method_id):
    """Delete a user's saved payment method."""
    method = get_object_or_404(UserPaymentMethod, pk=method_id, user=request.user)
    method.delete()
    return JsonResponse({'ok': True})


@login_required
def api_list_grouped(request):
    """Return saved methods grouped by account_number for the multi-select UI."""
    saved = UserPaymentMethod.objects.filter(
        user=request.user
    ).values_list('account_number', 'global_method_id')

    grouped = {}
    for acct, gmid in saved:
        grouped.setdefault(acct, []).append(gmid)

    return JsonResponse({
        'grouped': [
            {'account_number': num, 'global_method_ids': ids}
            for num, ids in grouped.items()
        ],
    })


@login_required
@require_POST
def api_batch_save(request):
    """Save a number for multiple payment methods at once.

    Expects JSON: {account_number: str, global_method_ids: [int, ...], old_account_number: str (optional)}
    If old_account_number is provided and differs from account_number, the old
    number's rows are deleted first (handles the edit-where-number-changed case).
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    account_number = data.get('account_number', '').strip()
    global_method_ids = data.get('global_method_ids', [])
    old_account_number = data.get('old_account_number', '').strip()

    if not account_number:
        return JsonResponse({'error': 'Account number is required'}, status=400)

    if not isinstance(global_method_ids, list):
        return JsonResponse({'error': 'global_method_ids must be a list'}, status=400)

    # If the number itself was changed during edit, clean up the old one
    if old_account_number and old_account_number != account_number:
        UserPaymentMethod.objects.filter(
            user=request.user, account_number=old_account_number,
        ).delete()

    valid_ids = set(
        GlobalPaymentMethod.objects.filter(
            is_active=True, pk__in=global_method_ids
        ).values_list('pk', flat=True)
    )

    for gmid in valid_ids:
        UserPaymentMethod.objects.update_or_create(
            user=request.user,
            global_method_id=gmid,
            defaults={'account_number': account_number, 'is_active': True},
        )

    # Remove methods that were unchecked for this number
    UserPaymentMethod.objects.filter(
        user=request.user,
        account_number=account_number,
    ).exclude(global_method_id__in=valid_ids).delete()

    return JsonResponse({'ok': True})


@login_required
@require_POST
def api_batch_delete(request):
    """Delete all saved methods for a given account number.

    Expects JSON: {account_number: str}
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    account_number = data.get('account_number', '').strip()
    if not account_number:
        return JsonResponse({'error': 'Account number is required'}, status=400)

    deleted, _ = UserPaymentMethod.objects.filter(
        user=request.user, account_number=account_number,
    ).delete()
    return JsonResponse({'ok': True, 'deleted': deleted})


@login_required
def api_used_methods(request):
    """Return global method IDs already used today by this user (across coin orders)."""
    today = date.today()

    coin_ids = set()
    coin_orders = Order.objects.filter(
        user=request.user, created_at__date=today, status='pending'
    ).prefetch_related('payments')
    for order in coin_orders:
        for p in order.payments.all():
            coin_ids.add(p.payment_method_id)

    return JsonResponse({
        'used_method_ids': sorted(coin_ids),
    })
