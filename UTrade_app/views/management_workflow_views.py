"""Management Orders / Pre-Orders. All the logic lives in workflow_core."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST

from ..models import Order, PreOrderRequest
from . import workflow_core as core


def is_management(user):
    return user.is_authenticated and getattr(user, 'user_role', None) == 'management'


def _scope():
    return core.Scope(
        key='management',
        order_qs=lambda: Order.objects.filter(seller__user_role='management'),
        preorder_qs=lambda: PreOrderRequest.objects.filter(seller__user_role='management'),
        urls={
            'order': ('management_orders', 'management_orders_batch'),
            'preorder': ('management_preorders', 'management_preorders_batch'),
        },
        titles={'order': 'CBRGU Orders', 'preorder': 'CBRGU Pre-Orders'},
    )


@login_required
@user_passes_test(is_management)
def management_orders(request):
    return core.board(request, 'order', _scope())


@login_required
@user_passes_test(is_management)
def management_preorders(request):
    return core.board(request, 'preorder', _scope())


@login_required
@user_passes_test(is_management)
@require_POST
def management_orders_batch(request):
    return core.batch(request, 'order', _scope())


@login_required
@user_passes_test(is_management)
@require_POST
def management_preorders_batch(request):
    return core.batch(request, 'preorder', _scope())