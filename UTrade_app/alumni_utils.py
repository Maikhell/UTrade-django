"""
UTrade_app/alumni_utils.py   (next to course_utils.py)

All alumni rules in one place. The registration page reads the same numbers
(passed to the template as data attributes), so the browser and the server agree.

A student number starts with the year the student ENTERED, e.g. 202311356 -> 2023.
Programs are PROGRAM_YEARS long and the academic year runs August -> July.

  year level   = (start year of the current academic year) - entry year + 1
  alumni       = year level is above PROGRAM_YEARS (they finished the program)
  graduation   = end of the last academic year   (July 31 of entry year + PROGRAM_YEARS)
  access ends  = graduation + ALUMNI_VALID_YEARS (their CvSU email stops working)

Example, today in Nov 2026 (academic year 2026-27):
  2023 -> level 4 -> regular student
  2022 -> level 5 -> alumnus, access until Jul 31, 2027
  2021 -> level 6 -> alumnus, but access ended Jul 31, 2026
"""
import calendar
from datetime import date

from django.utils import timezone

PROGRAM_YEARS = 4
ALUMNI_VALID_YEARS = 1            # how long alumni keep the account after graduating
ACADEMIC_YEAR_START_MONTH = 8     # August
ACADEMIC_YEAR_END_MONTH = 7       # July

# Student numbers whose entry year is more than this many calendar years back are
# rejected at registration (unchanged from the old script).
MAX_ENTRY_AGE_YEARS = 6


def _today(today=None):
    return today or timezone.localdate()


def entry_year(student_no):
    digits = (student_no or '').strip()
    if len(digits) < 4 or not digits[:4].isdigit():
        return None
    return int(digits[:4])


def academic_year_start(today=None):
    """2026 for any day from Aug 1, 2026 to Jul 31, 2027."""
    today = _today(today)
    return today.year if today.month >= ACADEMIC_YEAR_START_MONTH else today.year - 1


def year_level(student_no, today=None):
    year = entry_year(student_no)
    return None if year is None else academic_year_start(today) - year + 1


def can_claim_alumni(student_no, today=None):
    """True when the batch has finished the program (so 'alumnus' is a fair question)."""
    level = year_level(student_no, today)
    return level is not None and level > PROGRAM_YEARS


def alumni_expiry(student_no):
    """Last day of alumni access for this batch, or None."""
    year = entry_year(student_no)
    if year is None:
        return None
    end_year = year + PROGRAM_YEARS + ALUMNI_VALID_YEARS
    return date(end_year, ACADEMIC_YEAR_END_MONTH, calendar.monthrange(end_year, ACADEMIC_YEAR_END_MONTH)[1])


def alumni_window_open(student_no, today=None):
    expiry = alumni_expiry(student_no)
    return expiry is not None and expiry >= _today(today)


def alumni_signup_allowed(student_no, today=None):
    """Old enough to be an alumnus AND still inside the access window."""
    return can_claim_alumni(student_no, today) and alumni_window_open(student_no, today)