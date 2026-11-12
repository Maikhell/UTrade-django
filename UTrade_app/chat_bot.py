"""
UTrade Helper: a basic, rule-based assistant for the Messages page.

- The user can only pick from the predetermined QUESTIONS below (no free text).
- Each question has a fixed answer. Some answers are filled in from the user's
  own data (orders, account status, fee cycle) or from the item being discussed.
- An answer can carry links: the item, the seller's shop, or a page to go to.

WHO SEES WHAT (per account type)
- Students ........ buy only: orders, payments, meetups, item questions. No selling.
- Organizations ... sell only: shop, incoming orders, fees. No cart, no purchases, no buying.
- CBRGU / others .. both (unchanged).
Each question has an `audience`; the menu hides the others and the server refuses them.

To add a question: copy a @question block, give it a new id, topic and audience,
then return _reply("answer text", _link(...), ...).

Save as UTrade_app/chat_bot.py (next to models.py).
"""
from django.db.models import Avg, Count
from django.urls import reverse

from .models import Order, PreOrderRequest, Product, SellerReview, User

CBRGU_ROLES = ('management', 'cbrgu_staff')

# (key, title shown to the user, bootstrap icon)
TOPICS = [
    ('item', 'About this item', 'bi-box-seam'),
    ('orders', 'Orders & payments', 'bi-bag-check'),
    ('meetup', 'Meetups & pickup', 'bi-geo-alt'),
    ('shop', 'Managing your shop', 'bi-shop-window'),
    ('selling', 'Selling on UTrade', 'bi-shop'),
    ('account', 'Account & support', 'bi-person-gear'),
]

# audience values:
#   all      everyone
#   buyers   accounts that can buy (students, CBRGU, others)   -> NOT organizations
#   sellers  accounts that can sell (organizations, CBRGU, others) -> NOT students
#   students students only
#   orgs     organization accounts only
#   verifiable  students and other accounts that upload a COR / ID (not orgs, not CBRGU)
QUESTIONS = {}   # id -> definition (insertion order = display order)


def question(qid, topic, text, audience='all', needs_product=False):
    def register(fn):
        QUESTIONS[qid] = {
            'id': qid, 'topic': topic, 'text': text, 'audience': audience,
            'needs_product': needs_product, 'fn': fn,
        }
        return fn
    return register


# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #
def user_role(user):
    """kind + what the account may do. Students buy only; organizations sell only."""
    role = getattr(user, 'user_role', '')
    if getattr(user, 'is_org_account', False) or role == 'org_officer':
        kind = 'org'
    elif role in CBRGU_ROLES:
        kind = 'cbrgu'
    elif role == 'student':
        kind = 'student'
    else:
        kind = 'other'
    return {
        'kind': kind,
        'can_buy': kind != 'org',
        'can_sell': kind != 'student',
    }


def _visible(q, role):
    a = q['audience']
    if a == 'all':
        return True
    if a == 'buyers':
        return role['can_buy']
    if a == 'sellers':
        return role['can_sell']
    if a == 'students':
        return role['kind'] == 'student'
    if a == 'orgs':
        return role['kind'] == 'org'
    if a == 'verifiable':
        return role['kind'] in ('student', 'other')
    return False


def intro_for(user):
    kind = user_role(user)['kind']
    if kind == 'org':
        return "I can answer common questions about your shop, incoming orders, fees and your account."
    if kind == 'student':
        return "I can answer common questions about orders, payments, meetups and your account."
    return "I can answer common questions about orders, meetups, selling and your account."


def preview_for(user):
    kind = user_role(user)['kind']
    if kind == 'org':
        return "Ask about your shop, orders, fees and your account."
    return "Ask about orders, payments, meetups and your account."


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _link(label, url, icon='bi-box-arrow-up-right'):
    return {'label': label, 'url': url, 'icon': icon}


def _reply(text, *links):
    return {'text': text, 'links': [l for l in links if l]}


def _money(value):
    return f"₱{value:,.2f}"


def _seller_label(seller):
    """Name shown for a seller: CBRGU, the organization, or the student's name."""
    if seller is None:
        return 'the seller'
    if getattr(seller, 'user_role', '') in CBRGU_ROLES:
        return 'CBRGU'
    org = getattr(seller, 'org_link', None)
    if getattr(seller, 'is_org_account', False) or seller.user_role == 'org_officer':
        return (org.name if org else None) or seller.get_full_name() or 'the organization'
    return seller.get_full_name() or getattr(seller, 'display_name', None) or seller.username or 'the seller'


def _shop_link(seller, label=None):
    if seller is None:
        return None
    return _link(label or f"Visit {_seller_label(seller)}'s shop",
                 reverse('storefront', args=[seller.id]), 'bi-shop')


def _item_link(product, label=None):
    if product is None:
        return None
    return _link(label or f"View {product.name}", reverse('product.detail', args=[product.id]), 'bi-box-seam')


# Buyer-side links (never given to organization accounts)
_BROWSE = lambda: _link('Browse the marketplace', reverse('product.list'), 'bi-grid')
_PURCHASES = lambda: _link('Open My Purchases', reverse('order_history'), 'bi-bag-check')
_CART = lambda: _link('Open my cart', reverse('cart_detail'), 'bi-cart3')
# Shared links
_PROFILE = lambda: _link('Open my profile', reverse('user.profile'), 'bi-person-gear')
_MESSAGES = lambda: _link('Open Messages', reverse('inbox'), 'bi-chat-dots')
# Organization-side links
_ORG_PANEL = lambda: _link('Open the organization panel', reverse('organization.panel'), 'bi-speedometer2')
_ORG_ORDERS = lambda: _link('Open incoming orders', reverse('organization_orders'), 'bi-bag-check')
_ORG_PREORDERS = lambda: _link('Open pre-orders', reverse('organization_preorders'), 'bi-clock-history')
_ORG_PRODUCTS = lambda: _link('Open my products', reverse('org_products'), 'bi-box-seam')


def _time(t):
    return t.strftime('%I:%M %p').lstrip('0') if t else ''


# --------------------------------------------------------------------------- #
# Orders & payments (buyers only)
# --------------------------------------------------------------------------- #
@question('how_order', 'orders', 'How do I place an order?', audience='buyers')
def _how_order(user, product):
    return _reply(
        "1. Browse the marketplace and open an item.\n"
        "2. Choose a variant and add it to your cart.\n"
        "3. In your cart, select the items and press Proceed to Checkout.\n"
        "4. Pick a payment method for each seller and place your order.\n\n"
        "Items from different sellers become separate orders.",
        _BROWSE(), _CART(),
    )


@question('how_pay', 'orders', 'What payment methods are available?', audience='buyers')
def _how_pay(user, product):
    return _reply(
        "Each seller accepts Online GCash, Cash on Pickup, or both. You choose at checkout.\n\n"
        "• Online GCash: paid right away on a secure PayMongo page.\n"
        "• Cash on Pickup: paid in cash when you meet the seller.",
        _CART(),
    )


@question('where_order', 'orders', 'Where is my order?', audience='buyers')
def _where_order(user, product):
    order = (
        Order.objects.filter(user=user)
        .select_related('seller', 'seller__org_link').order_by('-created_at').first()
    )
    preorder = (
        PreOrderRequest.objects.filter(buyer=user)
        .select_related('seller', 'product_variant__product').order_by('-created_at').first()
    )
    if not order and not preorder:
        return _reply("You don't have any orders yet. Browse the marketplace to get started.", _BROWSE())

    lines, links = [], []
    if order:
        label = order.order_number or f"#{order.id}"
        lines.append(
            f"Your latest order {label} is {order.status}. "
            f"It is with {_seller_label(order.seller)}, total {_money(order.total_amount)}."
        )
        first = order.items.select_related('product_variant__product').first()
        links.append(_shop_link(order.seller))
        if first and first.product_variant:
            links.append(_item_link(first.product_variant.product))
    if preorder:
        name = preorder.product_variant.product.name
        lines.append(f"Your latest pre-order for {name} is {preorder.get_status_display()}.")
        if not order:
            links.append(_shop_link(preorder.seller))
            links.append(_item_link(preorder.product_variant.product, f"View {name}"))
    links.append(_PURCHASES())
    return _reply("\n".join(lines), *links)


@question('cancel_order', 'orders', 'Can I cancel an order?', audience='buyers')
def _cancel_order(user, product):
    return _reply(
        "Yes, while the order is still Pending (the seller hasn't accepted it yet). "
        "Open My Purchases and choose Cancel.\n\n"
        "After the seller accepts it, message the seller to ask for changes.",
        _PURCHASES(), _MESSAGES(),
    )


@question('receipt', 'orders', 'How do I get my receipt?', audience='buyers')
def _receipt(user, product):
    return _reply("Receipts are available for completed orders. Open My Purchases and download it from the order.",
                  _PURCHASES())


# --------------------------------------------------------------------------- #
# Meetups & pickup
# --------------------------------------------------------------------------- #
@question('where_meet', 'meetup', 'Where do I pick up my order?', audience='buyers')
def _where_meet(user, product):
    order = (
        Order.objects.filter(user=user)
        .exclude(status__in=('Completed', 'Cancelled', 'Rejected'))
        .select_related('seller', 'seller__org_link').order_by('-created_at').first()
    )
    if not order:
        return _reply("You have no open orders right now. Once you place one, I can tell you where to meet.",
                      _BROWSE())

    first = order.items.select_related('product_variant__product').first()
    prod = first.product_variant.product if first and first.product_variant else None
    place = (order.meetup_location or order.pickup_location or (prod.meetup_location_text if prod else '')).strip()

    lines = [f"Order {order.order_number or '#' + str(order.id)} with {_seller_label(order.seller)} is {order.status}."]
    lines.append(f"Meet at: {place}." if place else "The meetup spot isn't set yet. Message the seller to agree on one.")
    if prod and prod.available_days:
        lines.append(f"Available days: {prod.available_days}.")
    if prod and prod.preferred_meetup_time_from and prod.preferred_meetup_time_to:
        lines.append(f"Preferred time: {_time(prod.preferred_meetup_time_from)} to {_time(prod.preferred_meetup_time_to)}.")
    return _reply("\n".join(lines), _shop_link(order.seller), _MESSAGES())


@question('safe_meet', 'meetup', 'Is meeting up safe?')
def _safe_meet(user, product):
    return _reply(
        "Keep it safe:\n"
        "• Meet in public campus areas, during the day.\n"
        "• Check the item before you pay (or hand it over).\n"
        "• Never share passwords or one-time codes.\n"
        "• Keep your conversation in UTrade Messages.\n\n"
        "If something feels wrong, use Report user inside the conversation so CBRGU can review it.",
        _MESSAGES(),
    )


@question('no_show', 'meetup', "What if the seller doesn't show up?", audience='buyers')
def _no_show(user, product):
    return _reply(
        "Message the seller first to agree on a new time. "
        "If they don't reply or keep missing meetups, use Report user in the conversation and CBRGU will review it.",
        _MESSAGES(),
    )


# --------------------------------------------------------------------------- #
# Selling (not for students)
# --------------------------------------------------------------------------- #
@question('how_list', 'selling', 'How do I list an item?', audience='sellers')
def _how_list(user, product):
    if user_role(user)['kind'] == 'org':
        return _reply(
            "1. Open Add Product and fill in the details, variants, photos and meetup spot.\n"
            "2. Submit it. CBRGU reviews every listing before it goes live.\n"
            "3. Track it under My Products. Editing a live listing sends it back for review.",
            _link('Add a product', reverse('product.create'), 'bi-plus-circle'), _ORG_PRODUCTS(),
        )
    return _reply(
        "1. Make sure your account is verified.\n"
        "2. Open Add Product and fill in the details, variants, photos and meetup spot.\n"
        "3. Submit it. CBRGU reviews every listing before it goes live.",
        _link('Add a product', reverse('product.create'), 'bi-plus-circle'),
        _PROFILE(),
    )


@question('listing_pending', 'selling', 'Why is my listing still pending?', audience='sellers')
def _listing_pending(user, product):
    return _reply(
        "New listings, and edits to approved listings, are reviewed by CBRGU before they appear. "
        "You'll see the status change once it's approved or rejected.",
        _ORG_PRODUCTS() if user_role(user)['kind'] == 'org'
        else _link('Open my account', reverse('user.account'), 'bi-person'),
    )


@question('student_sell', 'selling', 'Can I sell my own items?', audience='students')
def _student_sell(user, product):
    return _reply(
        "Not as a student. On UTrade, students buy, while items are sold by CBRGU and student organizations.\n\n"
        "If you're an organization officer, your organization can sell through its own organization account "
        "(see \"I'm an organization officer\" under Account & support).",
        _PROFILE(), _BROWSE(),
    )


@question('ratings', 'selling', 'How do ratings work?')
def _ratings(user, product):
    role = user_role(user)
    if role['kind'] == 'student':
        return _reply(
            "After an order is completed, you can rate the products and the seller from My Purchases. "
            "Ratings and reviews show on the seller's shop.",
            _PURCHASES(),
        )
    if role['kind'] == 'org':
        return _reply(
            "After an order is completed, buyers can rate your products and your shop. "
            "Ratings and reviews appear on your shop page.",
            _shop_link(user, 'View our shop'),
        )
    return _reply(
        "After an order is completed, buyers can rate the products and the seller. "
        "Ratings and reviews show on the seller's shop.",
        _PURCHASES() if role['can_buy'] else None,
    )


# --------------------------------------------------------------------------- #
# Managing your shop (organization accounts only)
# --------------------------------------------------------------------------- #
@question('org_orders', 'shop', 'How do I handle incoming orders?', audience='orgs')
def _org_orders(user, product):
    incoming = Order.objects.filter(seller=user, status__in=('Pending', 'Paid')).count()
    accepted = Order.objects.filter(seller=user, status='Accepted').count()
    ready = Order.objects.filter(seller=user, status='Delivered').count()
    return _reply(
        f"Right now: {incoming} incoming, {accepted} accepted and {ready} ready for pickup.\n\n"
        "1. Accept (or reject, with a reason) each incoming order.\n"
        "2. Mark it ready for pickup when the items are prepared.\n"
        "3. Meet the buyer, then mark the order completed.",
        _ORG_ORDERS(), _MESSAGES(),
    )


@question('org_preorders', 'shop', 'How do pre-orders work for us?', audience='orgs')
def _org_preorders(user, product):
    pending = PreOrderRequest.objects.filter(
        seller=user, status__in=('PENDING', 'Pending', 'pending')
    ).count()
    return _reply(
        f"You have {pending} pending pre-order request{'s' if pending != 1 else ''}.\n\n"
        "Accept a request and give an estimated pickup time, update its progress as you prepare it, "
        "mark it ready, then complete it after the meetup.",
        _ORG_PREORDERS(),
    )


@question('org_products', 'shop', 'Where are my products and listings?', audience='orgs')
def _org_products(user, product):
    counts = {r['status']: r['n'] for r in
              Product.objects.filter(seller=user).values('status').annotate(n=Count('id')).order_by('status')}
    text = (
        "Your listings:\n"
        f"• Live: {counts.get('Approved', 0)}\n"
        f"• Waiting for CBRGU review: {counts.get('Pending', 0)}\n"
        f"• Unlisted: {counts.get('Unlisted', 0)}\n"
        f"• Rejected: {counts.get('Rejected', 0)}"
    )
    return _reply(text, _ORG_PRODUCTS(), _shop_link(user, 'View our shop'))


@question('org_payments', 'shop', 'How do buyers pay us?', audience='orgs')
def _org_payments(user, product):
    return _reply(
        "Each product has its own accepted payment: Online GCash, Cash on Pickup, or both.\n\n"
        "• Online GCash: the buyer pays on a secure PayMongo page, and the order shows as Paid.\n"
        "• Cash on Pickup: the buyer pays you in cash at the meetup.",
        _ORG_PRODUCTS(),
    )


@question('org_fee', 'shop', 'How does the platform fee work?', audience='orgs')
def _org_fee(user, product):
    text = ("Organization accounts pay a 3% platform fee on completed orders. "
            "The fee builds up in cycles and is remitted to CBRGU.")
    org = getattr(user, 'org_link', None)
    ledger = None
    if org is not None:
        ledger = org.fee_ledgers.exclude(status='PAID').order_by('-cycle_start').first()
    if ledger:
        days = ledger.days_until_due
        when = (f"{days} day{'s' if days != 1 else ''} left" if days >= 0 else f"overdue by {-days} day(s)")
        text += (f"\n\nCurrent cycle ends {ledger.cycle_due:%b %d, %Y} ({when}). "
                 f"Fee so far: {_money(ledger.accumulated_fee)}.")
    return _reply(
        text,
        _link('Open remittance', reverse('org_remittance_view'), 'bi-cash-coin'),
        _link('Remittance history', reverse('org_remittance_logs'), 'bi-receipt'),
    )


@question('org_noshow', 'shop', "What if a buyer doesn't show up?", audience='orgs')
def _org_noshow(user, product):
    return _reply(
        "Message the buyer to agree on a new time. "
        "If they keep missing meetups, use Report user in the conversation and CBRGU will review it.",
        _MESSAGES(),
    )


# --------------------------------------------------------------------------- #
# Account & support
# --------------------------------------------------------------------------- #
@question('how_verify', 'account', 'How do I get verified?', audience='verifiable')
def _how_verify(user, product):
    return _reply(
        "1. Complete your profile (name, student number, program, section).\n"
        "2. Upload your Certificate of Registration (COR).\n"
        "3. Wait for review. Your status changes to Verified once approved.",
        _PROFILE(),
    )


@question('my_status', 'account', 'What is my account status?', audience='verifiable')
def _my_status(user, product):
    status = (user.status or '').strip().lower()
    if status == 'verified':
        text = "Your account is Verified."
    elif status == 'pending':
        text = "Your account is Pending review. CBRGU is checking your documents, so there's nothing more to do for now."
    else:
        text = "Your account is not verified yet. Upload your COR in your profile to start trading."
    return _reply(text, _PROFILE())


@question('student_officer', 'account', "I'm an organization officer. How does my organization sell?", audience='students')
def _student_officer(user, product):
    managed = []
    try:
        managed = [rec.org_account for rec in user.managed_accounts]
    except Exception:
        managed = []
    text = (
        "1. Apply from your profile (Officer Application) with your organization, position and proof.\n"
        "2. CBRGU reviews it. If approved, your organization gets its own separate login for selling, "
        "and you're registered as the student accountable for it.\n"
        "3. Sign in with the organization's login ID to sell. Your personal student account stays a buying account."
    )
    if managed:
        names = ", ".join(
            f"{(a.org_link.name if getattr(a, 'org_link', None) else a.display_name or 'Organization')} "
            f"(login ID {a.student_no})" for a in managed
        )
        text += f"\n\nYou currently manage: {names}."
    return _reply(text, _PROFILE())


@question('org_manager', 'account', 'Who is accountable for this account?', audience='orgs')
def _org_manager(user, product):
    rec = getattr(user, 'active_manager', None)
    if not rec:
        return _reply("No student is linked to this account yet. Please contact CBRGU.", _PROFILE())
    since = getattr(rec, 'assigned_at', None)
    pos = f", {rec.position}" if getattr(rec, 'position', '') else ''
    when = f" since {since:%b %d, %Y}" if since else ''
    return _reply(
        f"{rec.student_name}{pos} is the student accountable for this account{when}.\n"
        "Only CBRGU can change the manager.",
        _PROFILE(),
    )


@question('org_cannot_buy', 'account', 'Can our organization account buy items?', audience='orgs')
def _org_cannot_buy(user, product):
    return _reply(
        "No. Organization accounts only sell; they don't have a cart or purchases. "
        "To buy, sign in with your personal student account."
    )


@question('contact_cbrgu', 'account', 'How do I contact CBRGU?')
def _contact_cbrgu(user, product):
    staff = User.objects.filter(user_role__in=CBRGU_ROLES).order_by('id').first()
    return _reply(
        "Open any CBRGU listing and tap Chat, or visit the CBRGU shop. "
        "To report a problem with another user, use Report user inside that conversation.",
        _shop_link(staff, 'Visit the CBRGU shop'),
    )


# --------------------------------------------------------------------------- #
# About this item (buyers, needs ?product=<id>)
# --------------------------------------------------------------------------- #
@question('item_available', 'item', 'Is this item available?', audience='buyers', needs_product=True)
def _item_available(user, product):
    if product.status != 'Approved':
        return _reply("This item isn't currently listed.", _shop_link(product.seller), _BROWSE())
    stock = product.get_total_stock
    if stock <= 0:
        text = f"{product.name} is out of stock right now."
        if product.pre_order:
            text += " It accepts pre-orders, so you can still request it."
    else:
        text = f"{product.name} is available: {stock} in stock, ₱{product.get_price_range}."
    return _reply(text, _item_link(product, 'Open the item'), _shop_link(product.seller))


@question('item_meetup', 'item', 'Where and when can I meet the seller?', audience='buyers', needs_product=True)
def _item_meetup(user, product):
    lines = []
    lines.append(f"Meetup spot: {product.meetup_location_text}." if product.meetup_location_text
                 else "The seller hasn't set a meetup spot. Message them to agree on one.")
    if product.available_days:
        lines.append(f"Available days: {product.available_days}.")
    if product.preferred_meetup_time_from and product.preferred_meetup_time_to:
        lines.append(f"Preferred time: {_time(product.preferred_meetup_time_from)} to "
                     f"{_time(product.preferred_meetup_time_to)}.")
    return _reply("\n".join(lines), _item_link(product, 'Open the item'), _shop_link(product.seller))


@question('item_payment', 'item', 'Which payments does this item accept?', audience='buyers', needs_product=True)
def _item_payment(user, product):
    label = {
        'GCASH': 'Online GCash only',
        'COP': 'Cash on Pickup only',
        'BOTH': 'Online GCash or Cash on Pickup',
    }.get(product.accepted_payments, 'Online GCash or Cash on Pickup')
    return _reply(f"This item accepts: {label}.", _item_link(product, 'Open the item'))


@question('item_seller', 'item', 'Who is selling this?', audience='buyers', needs_product=True)
def _item_seller(user, product):
    seller = product.seller
    agg = SellerReview.objects.filter(seller=seller).aggregate(avg=Avg('rating'), n=Count('id'))
    rating = f"Seller rating: {round(agg['avg'], 1)} / 5 from {agg['n']} review{'s' if agg['n'] != 1 else ''}." \
        if agg['n'] else "This seller has no ratings yet."
    text = f"This item is sold by {_seller_label(seller)}.\n{rating}\nSold so far: {product.sold} of this item."
    chat = None
    if seller.id != user.id:
        chat = _link('Message the seller', reverse('start_chat', args=[product.id]), 'bi-chat-dots')
    return _reply(text, _shop_link(seller), chat, _item_link(product, 'Open the item'))


@question('item_preorder', 'item', 'Is this a pre-order item?', audience='buyers', needs_product=True)
def _item_preorder(user, product):
    if product.pre_order:
        text = "Yes. This item is a pre-order: you send a request and the seller confirms it and tells you when it's ready."
    else:
        text = "No. This item is sold from stock; add it to your cart and check out."
    return _reply(text, _item_link(product, 'Open the item'))


# --------------------------------------------------------------------------- #
# Public API used by the views
# --------------------------------------------------------------------------- #
def build_menu(user, has_product):
    """Topics and questions this account may see. Topics with no questions are skipped."""
    role = user_role(user)
    menu = []
    for key, title, icon in TOPICS:
        if key == 'item' and not has_product:
            continue
        items = [
            {'id': q['id'], 'text': q['text']}
            for q in QUESTIONS.values()
            if q['topic'] == key and _visible(q, role)
        ]
        if items:
            menu.append({'key': key, 'title': title, 'icon': icon, 'questions': items})
    return menu


def answer(question_id, user, product_id=None):
    """Return {'question', 'text', 'links'} for a predetermined question, or None if unknown."""
    q = QUESTIONS.get(question_id)
    if not q:
        return None

    # Server-side check: hidden questions can't be asked by crafting a request.
    if not _visible(q, user_role(user)):
        return {
            'question': q['text'],
            **_reply("That question isn't available for your account type."),
        }

    product = None
    if q['needs_product']:
        if str(product_id or '').isdigit():
            product = (
                Product.objects.select_related('seller', 'seller__org_link')
                .filter(pk=int(product_id)).first()
            )
        if product is None:
            return {
                'question': q['text'],
                **_reply(
                    "Open the helper from an item's page or from a conversation about an item, "
                    "so I know which item you mean.",
                    _BROWSE(),
                ),
            }

    return {'question': q['text'], **q['fn'](user, product)}