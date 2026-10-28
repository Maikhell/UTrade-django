"""
UTrade_app/views/org_account_views.py

Add to urls.py:
    from .views import org_account_views            # add to the existing import list
    path('cbrgu/officer/<int:user_id>/approve/', org_account_views.approve_officer_application, name='approve_officer_application'),
    path('cbrgu/org-account/<int:org_user_id>/reassign/', org_account_views.reassign_org_manager, name='reassign_org_manager'),
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ..models import Organization, User
from ..org_accounts import assign_manager, create_org_account
from ..utils import log_action


def _is_cbrgu(user):
    return user.is_authenticated and user.user_role in ('management', 'cbrgu_staff')


@login_required
@user_passes_test(_is_cbrgu)
@require_POST
def approve_officer_application(request, user_id):
    """Approve a student's officer application: create the org login, or just name a new manager."""
    applicant = get_object_or_404(
        User, id=user_id, user_role='student', officer_status='pending'
    )
    # Form values look like "ITS - BSIT"; the Organization name is the first part.
    org_name = (applicant.organization or '').split(' - ')[0].strip()
    org = Organization.objects.filter(name__iexact=org_name).first()
    if not org:
        return JsonResponse(
            {'success': False, 'message': f'No Organization named "{org_name}".'}, status=400
        )

    password = None
    try:
        org_user = User.objects.filter(org_link=org, is_org_account=True).first()
        if org_user:
            assign_manager(org_user, applicant, assigned_by=request.user)
        else:
            org_user, password = create_org_account(org, applicant, assigned_by=request.user)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': ' '.join(e.messages)}, status=400)

    applicant.officer_status = 'verified'
    applicant.save(update_fields=['officer_status'])

    log_action(
        user=request.user, action='Officer Approved', item_type='Organization',
        item_name=org.name,
        details=f'{applicant.get_full_name()} ({applicant.student_no}) now manages {org_user.student_no}.',
    )
    return JsonResponse({
        'success': True,
        'org_login_id': org_user.student_no,
        'temporary_password': password,   # shown once; None if the org login already existed
    })


@login_required
@user_passes_test(_is_cbrgu)
@require_POST
def reassign_org_manager(request, org_user_id):
    """POST student_no=<new manager's student number>."""
    org_user = get_object_or_404(User, id=org_user_id, is_org_account=True)
    student = get_object_or_404(
        User, student_no=(request.POST.get('student_no') or '').strip(), user_role='student'
    )
    try:
        assign_manager(org_user, student, assigned_by=request.user)
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': ' '.join(e.messages)}, status=400)

    log_action(
        user=request.user, action='Org Manager Reassigned', item_type='Organization',
        item_name=org_user.org_link.name if org_user.org_link else org_user.student_no,
        details=f'New manager: {student.get_full_name()} ({student.student_no}).',
    )
    return JsonResponse({'success': True})