"""
UTrade_app/org_accounts.py  (next to models.py)
Helpers for organization logins and the student who is accountable for each.
"""
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import get_random_string

from .models import OrgAccountManager, User


def manager_note(user):
    """Text naming the accountable student, '' for normal users."""
    if not getattr(user, 'is_org_account', False):
        return ''
    m = user.active_manager
    if not m:
        return '[org account - no active manager]'
    return f'[managed by {m.student_name} ({m.student_no})]'


@transaction.atomic
def assign_manager(org_user, student, assigned_by=None, enforce=True):
    """Make `student` the single active manager of `org_user`; end the previous one."""
    if not org_user.is_org_account:
        raise ValidationError("That account is not an organization account.")
    if enforce and (
        student.user_role != 'student' or (student.status or '').lower() != 'verified'
    ):
        raise ValidationError("Only a verified student can manage an organization account.")

    current = org_user.manager_history.filter(is_active=True).first()
    if current and current.student_id == student.id:
        return current
    org_user.manager_history.filter(is_active=True).update(
        is_active=False, ended_at=timezone.now()
    )
    return OrgAccountManager.objects.create(
        org_account=org_user,
        student=student,
        student_name=student.get_full_name() or str(student),
        student_no=student.student_no,
        position=student.position or '',
        assigned_by=assigned_by,
    )


def _unique(base, exists, max_len):
    candidate, n = base[:max_len], 2
    while exists(candidate):
        suffix = f'-{n}'
        candidate = base[:max_len - len(suffix)] + suffix
        n += 1
    return candidate


@transaction.atomic
def create_org_account(org, student, assigned_by=None, enforce=True):
    """Create the org's own login. Returns (org_user, temporary_password)."""
    slug = re.sub(r'[^A-Za-z0-9]', '', org.name).upper() or f'ORG{org.id}'
    login_id = _unique(
        f'ORG-{slug}', lambda v: User.objects.filter(student_no=v).exists(), 20
    )
    email = _unique(
        f'org-{slug.lower()}@orgs.utrade.local',
        lambda v: User.objects.filter(email__iexact=v).exists(),
        254,
    )
    password = get_random_string(12)

    org_user = User(
        student_no=login_id,
        username=login_id,
        email=email,
        first_name=org.name,
        last_name='',
        user_role='org_officer',
        org_link=org,
        organization=org.name,
        is_org_account=True,
        is_officer=True,          # keeps existing is_officer checks (fees, owner_type) working
        officer_status='verified',
        status='verified',
        is_active=True,
        is_email_verified=True,
    )
    org_user.set_password(password)
    org_user.save()
    assign_manager(org_user, student, assigned_by=assigned_by, enforce=enforce)
    return org_user, password