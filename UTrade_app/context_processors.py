def payments_badge(request):
    u = getattr(request, "user", None)
    if u and u.is_authenticated and getattr(u, "user_role", "") == "management":
        from .models import OnlinePayment
        n = OnlinePayment.objects.filter(status="PAID", head_seen=False).count()
        return {"new_payments_count": n}
    return {}