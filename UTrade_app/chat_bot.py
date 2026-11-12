"""
UTrade Helper: a basic, rule-based assistant for the Messages page.

- The user can only pick from the predetermined QUESTIONS below (no free text).
- Each question has a fixed answer. Some answers are filled in from the user's
  own data (latest order, account status) or from the item being discussed.
- An answer can carry links: the item, the seller's shop, or a page to go to.

To add a question: copy one of the @question blocks, give it a new id, choose
its topic (see TOPICS) and return _reply("answer text", _link(...), ...).

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
    ('selling', 'Selling on UTrade', 'bi-shop'),
    ('account', 'Account & support', 'bi-person-gear'),
]

QUESTIONS = {}   # id -> question definition (insertion order = display order)


def question(qid, topic, text, needs_product=False):
    def register(fn):
        QUESTIONS[qid] = {
            'id': qid, 'topic': topic, 'text': text,
            'needs_product': needs_product, 'fn': fn,
        }
        return fn
    return register


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


_BROWSE = lambda: _link('Browse the marketplace', reverse('product.list'), 'bi-grid')
_PURCHASES = lambda: _link('Open My Purchases', reverse('order_history'), 'bi-bag-check')
_CART = lambda: _link('Open my cart', reverse('cart_detail'), 'bi-cart3')
_PROFILE = lambda: _link('Open my profile', reverse('user.profile'), 'bi-person-gear')
_MESSAGES = lambda: _link('Open Messages', reverse('inbox'), 'bi-chat-dots')


def _time(t):
    return t.strftime('%I:%M %p').lstrip('0') if t else ''


# --------------------------------------------------------------------------- #
# Orders & payments
# --------------------------------------------------------------------------- #
@question('how_order', 'orders', 'How do I place an order?')
def _how_order(user, product):
    return _reply(
        "1. Browse the marketplace and open an item.\n"
        "2. Choose a variant and add it to your cart.\n"
        "3. In your cart, select the items and press Proceed to Checkout.\n"
        "4. Pick a payment method for each seller and place your order.\n\n"
        "Items from different sellers become separate orders.",
        _BROWSE(), _CART(),
    )


@question('how_pay', 'orders', 'What payment methods are available?')
def _how_pay(user, product):
    return _reply(
        "Each seller accepts Online GCash, Cash on Pickup, or both. You choose at checkout.\n\n"
        "• Online GCash: paid right away on a secure PayMongo page.\n"
        "• Cash on Pickup: paid in cash when you meet the seller.",
        _CART(),
    )


@question('where_order', 'orders', 'Where is my order?')
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
        links.append(_item_link(preorder.product_variant.product, f"View {name}") if not order else None)
    links.append(_PURCHASES())
    return _reply("\n".join(lines), *links)


@question('cancel_order', 'orders', 'Can I cancel an order?')
def _cancel_order(user, product):
    return _reply(
        "Yes, while the order is still Pending (the seller hasn't accepted it yet). "
        "Open My Purchases and choose Cancel.\n\n"
        "After the seller accepts it, message the seller to ask for changes.",
        _PURCHASES(), _MESSAGES(),
    )


@question('receipt', 'orders', 'How do I get my receipt?')
def _receipt(user, product):
    return _reply("Receipts are available for completed orders. Open My Purchases and download it from the order.",
                  _PURCHASES())


# --------------------------------------------------------------------------- #
# Meetups & pickup
# --------------------------------------------------------------------------- #
@question('where_meet', 'meetup', 'Where do I pick up my order?')
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
        "• Check the item before you pay.\n"
        "• Never share passwords or one-time codes.\n"
        "• Keep your conversation in UTrade Messages.\n\n"
        "If something feels wrong, use Report user inside the conversation so CBRGU can review it.",
        _MESSAGES(),
    )


@question('no_show', 'meetup', "What if the seller doesn't show up?")
def _no_show(user, product):
    return _reply(
        "Message the seller first to agree on a new time. "
        "If they don't reply or keep missing meetups, use Report user in the conversation and CBRGU will review it.",
        _MESSAGES(),
    )


# --------------------------------------------------------------------------- #
# Selling
# --------------------------------------------------------------------------- #
@question('how_list', 'selling', 'How do I list an item?')
def _how_list(user, product):
    return _reply(
        "1. Make sure your account is verified.\n"
        "2. Open Add Product and fill in the details, variants, photos and meetup spot.\n"
        "3. Submit it. CBRGU reviews every listing before it goes live.",
        _link('Add a product', reverse('product.create'), 'bi-plus-circle'),
        _PROFILE(),
    )


@question('listing_pending', 'selling', 'Why is my listing still pending?')
def _listing_pending(user, product):
    return _reply(
        "New listings, and edits to approved listings, are reviewed by CBRGU before they appear. "
        "You'll see the status change once it's approved or rejected.",
        _link('Open my account', reverse('user.account'), 'bi-person'),
    )


@question('fees', 'selling', 'Are there selling fees?')
def _fees(user, product):
    return _reply(
        "Personal sellers pay no fee.\n"
        "Organization accounts pay a 3% platform fee on completed orders, remitted to CBRGU each cycle."
    )


@question('ratings', 'selling', 'How do ratings work?')
def _ratings(user, product):
    return _reply(
        "After an order is completed, buyers can rate the products and the seller. "
        "Ratings and reviews show on the seller's shop.",
        _PURCHASES(),
    )


# --------------------------------------------------------------------------- #
# Account & support
# --------------------------------------------------------------------------- #
@question('how_verify', 'account', 'How do I get verified?')
def _how_verify(user, product):
    return _reply(
        "1. Complete your profile (name, student number, program, section).\n"
        "2. Upload your Certificate of Registration (COR).\n"
        "3. Wait for review. Your status changes to Verified once approved.",
        _PROFILE(),
    )


@question('my_status', 'account', 'What is my account status?')
def _my_status(user, product):
    status = (user.status or '').strip().lower()
    if status == 'verified':
        text = "Your account is Verified. You can buy and sell."
    elif status == 'pending':
        text = "Your account is Pending review. CBRGU is checking your documents, so there's nothing more to do for now."
    else:
        text = "Your account is not verified yet. Upload your COR in your profile to start trading."
    return _reply(text, _PROFILE())


@question('contact_cbrgu', 'account', 'How do I contact CBRGU?')
def _contact_cbrgu(user, product):
    staff = User.objects.filter(user_role__in=CBRGU_ROLES).order_by('id').first()
    return _reply(
        "Open any CBRGU listing and tap Chat, or visit the CBRGU shop. "
        "To report a problem with another user, use Report user inside that conversation.",
        _shop_link(staff, 'Visit the CBRGU shop'),
    )


# --------------------------------------------------------------------------- #
# About this item (needs ?product=<id>)
# --------------------------------------------------------------------------- #
@question('item_available', 'item', 'Is this item available?', needs_product=True)
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


@question('item_meetup', 'item', 'Where and when can I meet the seller?', needs_product=True)
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


@question('item_payment', 'item', 'Which payments does this item accept?', needs_product=True)
def _item_payment(user, product):
    label = {
        'GCASH': 'Online GCash only',
        'COP': 'Cash on Pickup only',
        'BOTH': 'Online GCash or Cash on Pickup',
    }.get(product.accepted_payments, 'Online GCash or Cash on Pickup')
    return _reply(f"This item accepts: {label}.", _item_link(product, 'Open the item'))


@question('item_seller', 'item', 'Who is selling this?', needs_product=True)
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


@question('item_preorder', 'item', 'Is this a pre-order item?', needs_product=True)
def _item_preorder(user, product):
    if product.pre_order:
        text = "Yes. This item is a pre-order: you send a request and the seller confirms it and tells you when it's ready."
    else:
        text = "No. This item is sold from stock; add it to your cart and check out."
    return _reply(text, _item_link(product, 'Open the item'))


# --------------------------------------------------------------------------- #
# Public API used by the views
# --------------------------------------------------------------------------- #
def build_menu(has_product):
    """Topics with their questions, for the page. The 'item' topic needs an item."""
    menu = []
    for key, title, icon in TOPICS:
        if key == 'item' and not has_product:
            continue
        items = [
            {'id': q['id'], 'text': q['text']}
            for q in QUESTIONS.values() if q['topic'] == key
        ]
        if items:
            menu.append({'key': key, 'title': title, 'icon': icon, 'questions': items})
    return menu


def answer(question_id, user, product_id=None):
    """Return {'question', 'text', 'links'} for a predetermined question, or None if unknown."""
    q = QUESTIONS.get(question_id)
    if not q:
        return None

    product = None
    if q['needs_product']:
        if str(product_id or '').isdigit():
            product = (
                Product.objects.select_related('seller', 'seller__org_link')
                .filter(pk=int(product_id)).first()
            )
        if product is None:
            result = _reply(
                "Open the helper from an item's page or from a conversation about an item, "
                "so I know which item you mean.",
                _BROWSE(),
            )
            return {'question': q['text'], **result}

    result = q['fn'](user, product)
    return {'question': q['text'], **result}