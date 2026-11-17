"""
Single source of truth for every role's sidebar.
Only the *contents* differ per role; markup/styling live in _sidebar.html + sidebar.css.

Item keys (used for the `active` highlight):
  dashboard, active_listings, products, orders, preorders, payments, logs_reports,
  prohibited, categories, pickup_spots, add_accounts, all_users, remittance,
  payout, pending_verification, users, organizations, registered_users

url=None  -> rendered as a disabled placeholder link (href="#").
badge     -> name of a count (from sidebar_counts.py) or a template-context
             variable path (dotted allowed, e.g. "products.count").
alert     -> same kind of name; when it is truthy a small red dot is shown
             next to the label (used for the Dashboard item).
"""

HEAD, STAFF = "cbrgu_head", "cbrgu_staff"
ACADEMIC, NON_ACADEMIC, CSG = "academic_org", "non_academic_org", "csg_org"
OSAS, CASHIER = "osas_sds", "cashier"


def _i(key, label, icon, url, badge=None, badge_class="bg-success", always=False, alert=None):
    return {"key": key, "label": label, "icon": icon, "url": url,
            "badge": badge, "badge_class": badge_class, "always": always,
            "alert": alert}


# ---- CBRGU (head & staff share the same route names) -------------------
_C_DASH = _i("dashboard", "Dashboard", "bi-speedometer2", "dashboard",
             alert="alert_total")
_C_LIST = _i("active_listings", "Active Listings", "bi-check2-square", "active_listings",
             "pending_products_count", "bg-danger")
_C_PROD = _i("products", "Products", "bi-box-seam", "cbrgu_products",
             "total_products", "bg-light text-dark border", always=True)
_C_ORD = _i("orders", "Orders", "bi-inbox", "management_orders",
            "incoming_orders_count", "bg-danger")
_C_PRE = _i("preorders", "Pre Orders", "bi-calendar-check", "management_preorders",
            "incoming_preorder_count", "bg-danger")
_C_PAY = _i("payments", "Payments", "bi-credit-card-2-front", "management_payments",
            "new_payments_count", "bg-success")

# ---- Organizations ------------------------------------------------------
_O_DASH = _i("dashboard", "Dashboard", "bi-speedometer2", "organization.panel",
             alert="alert_total")
_O_PROD = _i("products", "Products", "bi-box-seam", "org_products",
             "products.count", "bg-light text-dark border", always=True,
             alert="pending_products_count")
_O_REM = _i("remittance", "Remittance", "bi-cash-stack", "org_remittance_view")
_O_ORD = _i("orders", "Orders", "bi-inbox", "organization_orders",
            "incoming_orders_count", "bg-danger")
_O_PRE = _i("preorders", "Pre Orders", "bi-calendar-check", "organization_preorders",
            "incoming_preorder_count", "bg-danger")
_O_PEND = _i("pending_verification", "Pending Verification", "bi-person-check",
             "org_pending_verification", "pending_verification_count", "bg-warning text-dark")
_O_USERS = _i("users", "Users", "bi-people", "org_users")

_ORG_BASE = [("Overview", [_O_DASH, _O_PROD, _O_REM]), ("Orders", [_O_ORD, _O_PRE])]

SIDEBARS = {
    HEAD: {
        "title": "CBRGU Panel", "add_product": True,
        "sections": [
            ("Overview", [_C_DASH, _C_LIST, _C_PROD]),
            ("Orders", [_C_ORD, _C_PRE]),
            ("Payments", [_C_PAY]),
            ("Settings", [
                _i("logs_reports", "Logs and Reports", "bi-journal-text", "logs_reports"),
                _i("prohibited", "Prohibited Items", "bi-exclamation-triangle", "add_prohibited_words"),
                _i("categories", "Categories", "bi-tags", "add_categories"),
                _i("pickup_spots", "Pickup Spots", "bi-geo-alt", "add_pickup_spots"),
            ]),
            ("Admin", [
                _i("add_accounts", "Add Accounts", "bi-person-add", "add_accounts"),
                _i("all_users", "All Users", "bi-people", "all_users"),
            ]),
        ],
    },
    STAFF: {
        "title": "CBRGU Panel", "add_product": True,
        "sections": [("Overview", [_C_DASH, _C_LIST, _C_PROD]), ("Orders", [_C_ORD, _C_PRE])],
    },
    ACADEMIC: {
        "title": "{org} Panel", "add_product": True,
        "sections": _ORG_BASE + [("Users", [_O_PEND, _O_USERS])],
    },
    NON_ACADEMIC: {"title": "{org} Panel", "add_product": True, "sections": _ORG_BASE},
    # CSG = Academic minus Pending Verification and Users
    CSG: {"title": "{org} Panel", "add_product": True, "sections": _ORG_BASE},
    OSAS: {
        "title": "OSAS / SDS Panel", "add_product": False,
        "sections": [("Overview", [
            _i("organizations", "Organizations", "bi-building", "osas_organizations"),
            _i("registered_users", "All Registered Users", "bi-people", "osas_registered_users"),
        ])],
    },
    CASHIER: {
        "title": "Cashier Panel", "add_product": False,
        "sections": [("Overview", [
            # Remittance moved here from the CBRGU sidebar (same route, unchanged)
            _i("remittance", "Remittance", "bi-cash-stack", "remittance_management"),
            _i("payout", "Payout", "bi-wallet2", None),   # URL intentionally blank for now
        ])],
    },
}

# Your User.user_role value -> sidebar role key
USER_ROLE_MAP = {
    "cbrgu_staff": STAFF,
    "management": HEAD,      # assumption: Management = CBRGU head. Change if wrong.
    "osas_sds": OSAS,
    "cashier": CASHIER,
}


def get_sidebar_role(user, org=None):
    """Map a request user (+ optional org) to a sidebar role key."""
    if user is not None and getattr(user, "is_authenticated", False):
        mapped = USER_ROLE_MAP.get(getattr(user, "user_role", ""))
        if mapped:
            return mapped

    # Organization officers / org accounts -> pick by org type
    if org is not None:
        if (getattr(org, "org_type", "academic") or "academic") != "academic":
            return NON_ACADEMIC
        return CSG if (org.name or "").upper() == "CSG" else ACADEMIC

    return None