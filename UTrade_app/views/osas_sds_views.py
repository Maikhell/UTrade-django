# osas_sds_views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Value, Q
from django.db.models.functions import Coalesce
from django.shortcuts import render

from ..models import Organization, User, Product


def is_osas_sds(user):
    return user.is_authenticated and getattr(user, 'user_role', None) == 'osas_sds'


def _osas_sidebar_context():
    """Minimal stats for OSAS/SDS sidebar."""
    total_orgs = Organization.objects.count()
    total_students = User.objects.filter(user_role='student').count()
    return {
        'total_organizations': total_orgs,
        'total_students': total_students,
        'total_users': User.objects.count(),
    }


@login_required
@user_passes_test(is_osas_sds)
def osas_organizations(request):
    """
    OSAS/SDS – list organizations with holder account + View Shop link.
    Read-only. No remittance / management actions.
    """
    search = request.GET.get('search', '').strip()

    # Holder: prefer is_officer=True, fallback to any linked user
    holder_officer_qs = User.objects.filter(
        org_link=OuterRef('pk'),
        is_officer=True,
    ).order_by('id')

    holder_any_qs = User.objects.filter(
        org_link=OuterRef('pk'),
    ).order_by('id')

    qs = Organization.objects.annotate(
        holder_id=Coalesce(
            Subquery(holder_officer_qs.values('id')[:1]),
            Subquery(holder_any_qs.values('id')[:1]),
        ),
        holder_display=Coalesce(
            Subquery(holder_officer_qs.values('display_name')[:1]),
            Subquery(holder_officer_qs.values('first_name')[:1]),
            Subquery(holder_any_qs.values('display_name')[:1]),
            Subquery(holder_any_qs.values('first_name')[:1]),
            Value('—'),
        ),
        holder_username=Coalesce(
            Subquery(holder_officer_qs.values('username')[:1]),
            Subquery(holder_any_qs.values('username')[:1]),
            Value(''),
        ),
    ).order_by('name')

    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(full_name__icontains=search)
            | Q(course_code__icontains=search)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        **_osas_sidebar_context(),
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'UTrade_app/osas_sds/organizations.html', context)


@login_required
@user_passes_test(is_osas_sds)
def osas_registered_users(request):
    """
    OSAS/SDS – view all registered students (and optionally other users).
    Read-only list.
    """
    search = request.GET.get('search', '').strip()
    role = request.GET.get('role', 'student').strip()  # default students

    qs = User.objects.all().order_by('-date_joined')

    if role:
        qs = qs.filter(user_role=role)

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(student_no__icontains=search)
            | Q(display_name__icontains=search)
            | Q(username__icontains=search)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        **_osas_sidebar_context(),
        'page_obj': page_obj,
        'search': search,
        'role_filter': role,
        'total_filtered': qs.count(),
    }
    return render(request, 'UTrade_app/osas_sds/registered_users.html', context)