"""
Who may order or pre-order a product.

General listings are open to every student. A private listing, which only academic
organizations can create (not CSG, non-academic organizations or Management), can only
be bought by students of the organization's program (e.g. ITS -> BSIT).
"""
from .course_utils import course_matches

AUDIENCE_GENERAL = 'GENERAL'
AUDIENCE_PRIVATE = 'PRIVATE'


def org_restriction_course(org):
    """Program code an organization's private listings are limited to, or None."""
    if org is None:
        return None
    if (getattr(org, 'org_type', '') or '').lower() != 'academic':
        return None
    if (getattr(org, 'name', '') or '').upper() == 'CSG':
        return None
    return (getattr(org, 'course_code', '') or '').strip() or None


def seller_restriction_course(user):
    """
    Program code this seller's private listings would be limited to.
    None means the seller can't make private listings (not an organization seller,
    Management, CSG or a non-academic organization).
    """
    if not getattr(user, 'is_authenticated', False):
        return None
    role = getattr(user, 'user_role', None)
    if role == 'management':
        return None
    if not (getattr(user, 'is_officer', False) or role == 'org_officer'):
        return None
    return org_restriction_course(getattr(user, 'org_link', None))


def product_org(product):
    org = getattr(product, 'related_org', None)
    if org is not None:
        return org
    return getattr(getattr(product, 'seller', None), 'org_link', None)


def product_restriction_course(product):
    """Program code a product is limited to; None for a general product."""
    if getattr(product, 'audience', AUDIENCE_GENERAL) != AUDIENCE_PRIVATE:
        return None
    return org_restriction_course(product_org(product))


def purchase_block_reason(user, product):
    """Why `user` can't order or pre-order `product`, or None when they can."""
    code = product_restriction_course(product)
    if not code:
        return None
    if not getattr(user, 'is_authenticated', False):
        return None                      # signing in is handled elsewhere
    course = (getattr(user, 'course', '') or '').strip()
    if course and course_matches(course, code):
        return None
    return f'This is a private listing for {code} students only.'


def first_purchase_block(user, products):
    """First blocking message across several products, or None."""
    for product in products:
        reason = purchase_block_reason(user, product)
        if reason:
            return f'{product.name}: {reason}'
    return None


def blocked_cart_reason(user, cart_items):
    """Same check for CartItem rows (used at checkout)."""
    return first_purchase_block(user, (item.variant.product for item in cart_items))