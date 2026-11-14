"""Numbers and badges for the product page: seller card and review summary."""
from django.db.models import Avg, Count, Sum

TOP_RATED_MIN_AVG = 4.5
TOP_RATED_MIN_REVIEWS = 5
TRUSTED_MIN_SOLD = 50


def _pct(avg):
    return int(round(max(0.0, min(5.0, avg)) / 5 * 100))


def seller_summary(seller, product=None):
    from .models import Product, SellerReview   # imported here to avoid import cycles

    ratings = SellerReview.objects.filter(seller=seller).aggregate(avg=Avg('rating'), n=Count('id'))
    avg = round(float(ratings['avg'] or 0), 1)
    count = ratings['n'] or 0

    totals = Product.objects.filter(seller=seller, status='Approved').aggregate(
        items=Count('id'), sold=Sum('sold')
    )
    sold = totals['sold'] or 0

    role = getattr(seller, 'user_role', '') or ''
    official = role in ('management', 'admin', 'campus_admin')

    badges = []
    if official:
        badges.append({'label': 'Official', 'icon': 'bi-patch-check-fill', 'tone': 'official'})
    elif product is not None and getattr(product, 'owner_type', '') == 'ORGANIZATION':
        org = getattr(product, 'related_org', None) or getattr(seller, 'org_link', None)
        badges.append({'label': org.name if org else 'Organization',
                       'icon': 'bi-people-fill', 'tone': 'org'})
    if not official and (getattr(seller, 'status', '') or '').lower() == 'verified':
        badges.append({'label': 'Verified', 'icon': 'bi-shield-check', 'tone': 'verified'})
    if count >= TOP_RATED_MIN_REVIEWS and avg >= TOP_RATED_MIN_AVG:
        badges.append({'label': 'Top Rated', 'icon': 'bi-star-fill', 'tone': 'top'})
    if sold >= TRUSTED_MIN_SOLD:
        badges.append({'label': 'Trusted Seller', 'icon': 'bi-bag-check-fill', 'tone': 'trusted'})

    return {
        'avg': avg,
        'pct': _pct(avg),
        'count': count,
        'products': totals['items'] or 0,
        'sold': sold,
        'badges': badges,
    }


def review_summary(product):
    from .models import Review

    qs = Review.objects.filter(product=product)
    agg = qs.aggregate(avg=Avg('rating'), n=Count('id'))
    n = agg['n'] or 0
    avg = round(float(agg['avg'] or 0), 1)
    counts = {row['rating']: row['c'] for row in qs.values('rating').annotate(c=Count('id'))}
    rows = [
        {
            'stars': s,
            'count': counts.get(s, 0),
            'pct': int(round(counts.get(s, 0) * 100 / n)) if n else 0,
        }
        for s in (5, 4, 3, 2, 1)
    ]
    return {
        'avg': avg,
        'pct': _pct(avg),
        'count': n,
        'rows': rows,
        'with_media': qs.filter(media__isnull=False).distinct().count(),
    }