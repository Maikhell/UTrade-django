PENDING_PREORDER = ["PENDING", "Pending", "pending"]
CBRGU_ROLES = {"management", "cbrgu_staff"}


def get_sidebar_counts(user, org=None):
    counts = {
        "incoming_orders_count": 0,
        "incoming_preorder_count": 0,
        "pending_products_count": 0,
        "alert_total": 0,
    }
    if not getattr(user, "is_authenticated", False):
        return counts

    from UTrade_app.models import Order, PreOrderRequest, Product  # avoid circular import

    if getattr(user, "user_role", "") in CBRGU_ROLES:
        orders = Order.objects.filter(seller__user_role="management", status__in=["Pending", "Paid"])
        pre = PreOrderRequest.objects.filter(seller__user_role="management", status__in=PENDING_PREORDER)
        prods = Product.objects.filter(status="Pending")
    else:
        org = org or getattr(user, "org_link", None)
        if org is None:
            return counts
        orders = Order.objects.filter(seller__org_link=org, status__in=["Pending", "Paid"])
        pre = PreOrderRequest.objects.filter(seller__org_link=org, status__in=PENDING_PREORDER)
        prods = Product.objects.filter(related_org=org, status="Pending")

    counts["incoming_orders_count"] = orders.count()
    counts["incoming_preorder_count"] = pre.count()
    counts["pending_products_count"] = prods.count()
    counts["alert_total"] = (
        counts["incoming_orders_count"]
        + counts["incoming_preorder_count"]
        + counts["pending_products_count"]
    )
    return counts