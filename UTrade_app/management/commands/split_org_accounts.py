from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
 
from UTrade_app.models import Order, Organization, PreOrderRequest, Product, User
from UTrade_app.org_accounts import create_org_account
 
 
class Command(BaseCommand):
    help = "Create a separate login per organization and turn current officers back into students."
 
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
 
    def handle(self, *args, **opts):
        dry = opts['dry_run']
        with transaction.atomic():
            for org in Organization.objects.all():
                self._split(org)
            if dry:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING('DRY RUN - nothing was saved.'))
 
    def _split(self, org):
        if User.objects.filter(org_link=org, is_org_account=True).exists():
            self.stdout.write(f'[{org.name}] already has an org account - skipped')
            return
 
        officers = list(
            User.objects.filter(org_link=org, is_org_account=False)
            .exclude(user_role='alumni_assoc')
            .filter(Q(is_officer=True) | Q(user_role='org_officer'))
        )
        if not officers:
            self.stdout.write(f'[{org.name}] no officers found - skipped')
            return
 
        manager = next(
            (u for u in officers if (u.position or '').strip().lower() == 'president'),
            officers[0],
        )
        org_user, password = create_org_account(org, manager, enforce=False)
 
        n_prod = Product.objects.filter(seller__in=officers).update(seller=org_user)
        n_ord = Order.objects.filter(seller__in=officers).update(seller=org_user)
        n_pre = PreOrderRequest.objects.filter(seller__in=officers).update(seller=org_user)
 
        User.objects.filter(id__in=[u.id for u in officers]).update(
            user_role='student', is_officer=False, org_link=None
        )
 
        self.stdout.write(self.style.SUCCESS(
            f'[{org.name}] login={org_user.student_no} password={password} '
            f'manager={manager.get_full_name()} ({manager.student_no}) '
            f'moved: {n_prod} products, {n_ord} orders, {n_pre} pre-orders; '
            f'{len(officers)} officer(s) -> student'
        ))
 