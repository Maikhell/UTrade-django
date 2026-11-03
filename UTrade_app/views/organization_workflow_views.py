"""Organization Orders / Pre-Orders: same workflow, UI and notifications as Management."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST

from . import workflow_core as core
from .organization_views import (
    _org_order_qs,
    _org_preorder_qs,
    _org_product_qs,
    _require_org,
    is_organization,
)


def _scope(request):
    user = request.user
    org = _require_org(user)
    org_name = org.name if org else 'Organization'

    def line_filter(item):
        """Show an organization only the items that belong to it."""
        variant = item.product_variant
        product = variant.product if variant else None
        if product is None:
            return True                     # deleted product: keep it visible
        seller = product.seller
        return product.seller_id == user.id or (
            org is not None and getattr(seller, 'org_link_id', None) == org.id
        )

    def extra_context():
        return {
            'org': org,
            'org_name': org_name,
            'products': _org_product_qs(user),
            'incoming_preorder_count': _org_preorder_qs(user).filter(
                status__in=core.PREORDER_STATUSES['incoming']
            ).count(),
        }

    return core.Scope(
        key='organization',
        actor_label=org_name,
        order_qs=lambda: _org_order_qs(user),
        preorder_qs=lambda: _org_preorder_qs(user),
        urls={
            'order': ('organization_orders', 'organization_orders_batch'),
            'preorder': ('organization_preorders', 'organization_preorders_batch'),
        },
        titles={
            'order': f'{org_name} Orders',
            'preorder': f'{org_name} Pre-Orders',
        },
        extra_context=extra_context,
        line_filter=line_filter,
        accrue_fees=True,
    )


@login_required
@user_passes_test(is_organization)
def organization_orders(request):
    return core.board(request, 'order', _scope(request))


@login_required
@user_passes_test(is_organization)
def organization_preorders(request):
    return core.board(request, 'preorder', _scope(request))


@login_required
@user_passes_test(is_organization)
@require_POST
def organization_orders_batch(request):
    return core.batch(request, 'order', _scope(request))


@login_required
@user_passes_test(is_organization)
@require_POST
def organization_preorders_batch(request):
    return core.batch(request, 'preorder', _scope(request))