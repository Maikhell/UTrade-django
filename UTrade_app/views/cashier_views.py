"""
Cashier: records platform-fee remittances and issues the receipts.

Moved here from management_views.py. CBRGU management can now only VIEW the
remittance cycles and NOTIFY organizations; closing a cycle is the cashier's job.

Only accounts with user_role == 'cashier' can open anything in this module:
anonymous visitors are sent to the login page, everyone else gets a 403.
"""
import logging
import re
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Q, Subquery, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import Organization, OrganizationPlatformLedger, PlatformFeeRemittance
from ..utils import log_action

logger = logging.getLogger(__name__)

RECEIPT_NO_PATTERN = re.compile(r'\d{7}')


# --------------------------------------------------------------------------- #
# Access control
# --------------------------------------------------------------------------- #
def is_cashier(user):
    return user.is_authenticated and getattr(user, 'user_role', None) == 'cashier'


def cashier_required(view_func):
    """Login required, and the account must be a cashier (403 for anyone else)."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_cashier(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped


# --------------------------------------------------------------------------- #
# Remittance board
# --------------------------------------------------------------------------- #
@cashier_required
def cashier_remittance(request):
    """Every organization with its latest cycle, plus the receipts already issued."""
    search = (request.GET.get('q') or '').strip()
    today = timezone.localdate()

    # Latest ledger per organization (unpaid first, then newest cycle)
    latest = OrganizationPlatformLedger.objects.filter(
        organization=OuterRef('pk')
    ).order_by('status', '-cycle_start')

    organizations = Organization.objects.annotate(
        latest_ledger_id=Subquery(latest.values('id')[:1]),
        cycle_start=Subquery(latest.values('cycle_start')[:1]),
        cycle_due=Subquery(latest.values('cycle_due')[:1]),
        accumulated_sales=Subquery(latest.values('accumulated_sales')[:1]),
        accumulated_fee=Subquery(latest.values('accumulated_fee')[:1]),
        status=Subquery(latest.values('status')[:1]),
    ).order_by('name')
    if search:
        organizations = organizations.filter(
            Q(name__icontains=search) | Q(full_name__icontains=search)
        )
    page_obj = Paginator(organizations, 25).get_page(request.GET.get('page'))

    open_ledgers = OrganizationPlatformLedger.objects.exclude(
        status=OrganizationPlatformLedger.STATUS_PAID
    )
    issued_today = PlatformFeeRemittance.objects.filter(payment_date=today)

    receipts = (
        PlatformFeeRemittance.objects
        .select_related('ledger__organization', 'recorded_by')
        .order_by('-payment_date', '-created_at')[:50]
    )

    return render(request, 'UTrade_app/cashier/remittance.html', {
        'page_obj': page_obj,
        'search': search,
        'today': today,
        'receipts': receipts,
        'summary': {
            'outstanding': open_ledgers.aggregate(s=Sum('accumulated_fee'))['s'] or Decimal('0.00'),
            'overdue': open_ledgers.filter(cycle_due__lt=today).count(),
            'issued_today': issued_today.count(),
            'collected_today': issued_today.aggregate(s=Sum('amount_paid'))['s'] or Decimal('0.00'),
        },
    })


# --------------------------------------------------------------------------- #
# Record a payment (mark paid, issue the receipt, start the next cycle)
# --------------------------------------------------------------------------- #
@cashier_required
@require_POST
def record_platform_remittance(request):
    """
    Mark a cycle as paid, issue the receipt and open the next 30-day cycle.
    The cashier types a 7-digit receipt number; it becomes the receipt number
    printed on the receipt, and it can only be used once.
    """
    ledger_id = (request.POST.get('ledger_id') or '').strip()
    receipt_no = (request.POST.get('receipt_no') or '').strip()
    received_by = (
        (request.POST.get('received_by') or '').strip()
        or request.user.get_full_name()
        or str(request.user)
    )
    notes = (request.POST.get('notes') or '').strip()

    if not RECEIPT_NO_PATTERN.fullmatch(receipt_no):
        messages.error(request, 'Enter the receipt number as exactly 7 digits.')
        return redirect('cashier_remittance')
    if not ledger_id.isdigit():
        messages.error(request, 'No remittance cycle was selected.')
        return redirect('cashier_remittance')

    with transaction.atomic():
        # Lock the row so a double click or two cashiers can't record the same cycle twice
        ledger = (
            OrganizationPlatformLedger.objects.select_for_update()
            .select_related('organization').filter(id=int(ledger_id)).first()
        )
        if not ledger or ledger.status == OrganizationPlatformLedger.STATUS_PAID:
            messages.warning(request, 'This remittance cycle is already marked as paid or does not exist.')
            return redirect('cashier_remittance')
        if ledger.accumulated_fee <= 0:
            messages.error(request, 'There is no platform fee to collect for this cycle.')
            return redirect('cashier_remittance')
        if PlatformFeeRemittance.objects.filter(receipt_no=receipt_no).exists():
            messages.error(request, f'Receipt number {receipt_no} has already been used.')
            return redirect('cashier_remittance')

        today = timezone.localdate()
        try:
            with transaction.atomic():
                rem = PlatformFeeRemittance.objects.create(
                    ledger=ledger,
                    amount_paid=ledger.accumulated_fee,
                    payment_date=today,
                    due_date=ledger.cycle_due,
                    management_rep_name=received_by[:120],
                    recorded_by=request.user,
                    receipt_no=receipt_no,
                    notes=notes,
                )
        except IntegrityError:
            messages.error(request, f'Receipt number {receipt_no} has already been used.')
            return redirect('cashier_remittance')

        ledger.status = OrganizationPlatformLedger.STATUS_PAID
        ledger.save(update_fields=['status', 'updated_at'])

        # Fresh open cycle starting today (+30 days)
        OrganizationPlatformLedger.objects.create(
            organization=ledger.organization,
            cycle_start=today,
            cycle_due=today + timedelta(days=30),
            status=OrganizationPlatformLedger.STATUS_OPEN,
            accumulated_fee=Decimal('0.00'),
            accumulated_sales=Decimal('0.00'),
        )

    log_action(
        user=request.user,
        action='Remittance Recorded',
        item_type='Organization',
        item_name=str(ledger.organization.name),
        details=f'Receipt {receipt_no} · ₱{rem.amount_paid} · received by {received_by}.',
    )
    messages.success(request, f'Remittance recorded. Receipt {receipt_no} generated.')
    return redirect('platform_fee_receipt', remittance_id=rem.id)


# --------------------------------------------------------------------------- #
# Receipt
# --------------------------------------------------------------------------- #
@cashier_required
def platform_fee_receipt(request, remittance_id):
    """View / print a platform fee receipt (shows the cashier's 7-digit receipt number)."""
    rem = get_object_or_404(
        PlatformFeeRemittance.objects.select_related('ledger__organization', 'recorded_by'),
        id=remittance_id,
    )
    return render(request, 'UTrade_app/reports/platform_fee_receipt.html', {
        'rem': rem,
        'org': rem.ledger.organization,
    })
