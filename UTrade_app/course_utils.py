"""
Course / major helpers for UTrade.

Place this file next to models.py (UTrade_app/course_utils.py).

- COURSE_CHOICES : used by the profile page (and should be reused by the
                   register form) so every screen shows the same list.
- PROGRAM_OF     : majors that still belong to one parent program/org.
- course_q()     : Q filter that matches every course belonging to an org.
- course_matches(): same check for a single user (True/False).
"""
from functools import reduce
from operator import or_

from django.db.models import Q

# (code stored in DB, label shown after the code in the dropdown)
COURSE_CHOICES = [
    ("BSIT", "Bachelor of Science in Information Technology"),
    ("BSHM", "Bachelor of Science in Hospitality Management"),
    ("BSCS", "Bachelor of Science in Computer Science"),
    ("BSEd-MATH", "Bachelor of Science in Education - Mathematics"),
    ("BSEd-ENG", "Bachelor of Science in Education - English"),
    ("BSBA-HR", "Bachelor of Science in Business Administration - Human Resource"),
    ("BSBA-MM", "Bachelor of Science in Business Administration - Marketing Management"),
    ("BSP", "Bachelor of Science in Psychology"),
    ("BSC", "Bachelor of Science in Criminology"),
]

VALID_COURSE_CODES = {code for code, _ in COURSE_CHOICES}

# Majors -> the parent program they still belong to.
PROGRAM_OF = {
    "BSBA-HR": "BSBA",
    "BSBA-MM": "BSBA",
    "BSEd-MATH": "BSED",
    "BSEd-ENG": "BSED",
}

# Old codes that may still exist in the database.
LEGACY_PROGRAM = {
    "BSBM": "BSBA",
    "BSE": "BSED",
    "BSED": "BSED",
}

# Society (organization) each course belongs to.
COURSE_SOCIETY = {
    "BSIT": "ITS",
    "BSCS": "ACS",
    "BSHM": "BSHMS",
    "BSEd-MATH": "TES",
    "BSEd-ENG": "TES",
    "BSBA-MM": "LMS-JMA",
    "BSBA-HR": "SHR",
    "BSC": "LCDCS",
    "BSP": "LLP",
}


def _norm(value):
    return (value or "").strip().upper()


_PROGRAM_OF = {_norm(k): v for k, v in PROGRAM_OF.items()}
_LEGACY = {_norm(k): v for k, v in LEGACY_PROGRAM.items()}
_MAJOR_KEYS = set(_PROGRAM_OF)
_ALL_CODES = [c for c, _ in COURSE_CHOICES] + list(LEGACY_PROGRAM)


def program_of(code):
    """Parent program of a course code (the code itself if it has none)."""
    key = _norm(code)
    return _PROGRAM_OF.get(key) or _LEGACY.get(key) or key


def society_of(code):
    return COURSE_SOCIETY.get(code, "")


def matching_courses(org_code):
    """
    Course codes that belong to an organization whose course_code is `org_code`.

    org_code "BSBA"    -> BSBA-HR, BSBA-MM (+ legacy BSBM)
    org_code "BSBA-MM" -> BSBA-MM only
    org_code "BSED"    -> BSEd-MATH, BSEd-ENG (+ legacy BSE)
    org_code "BSIT"    -> BSIT
    """
    key = _norm(org_code)
    if not key:
        return []
    if key in _MAJOR_KEYS:
        return [c for c in _ALL_CODES if _norm(c) == key]
    prog = program_of(key)
    return [c for c in _ALL_CODES if _norm(c) == key or program_of(c) == prog]


def course_q(org_code, field="course"):
    """Q object: users (or rows) whose `field` belongs to this org."""
    codes = matching_courses(org_code) or [org_code]
    return reduce(or_, (Q(**{f"{field}__iexact": c}) for c in codes))


def course_matches(user_course, org_code):
    """True if a user's course belongs to the org with this course_code."""
    codes = matching_courses(org_code) or [org_code]
    return _norm(user_course) in {_norm(c) for c in codes}