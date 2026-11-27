from datetime import datetime, timezone, timedelta

import pytest

from azos import utils
from azos.utils import (
    unzone, unzone_null,
    align_minutes, align_minutes_null,
    align_hour, align_hour_null,
    align_30min, align_30min_null,
    align_20min, align_20min_null,
    align_15min, align_15min_null,
    align_midnight, align_midnight_null,
    align_month_first, align_month_first_null,
    align_sunday, align_sunday_null,
    align_monday, align_monday_null,
)

EST = timezone(timedelta(hours=-5))

# (non-null function, null-tolerant function) - all single-argument
PAIRS = [
    (unzone, unzone_null),
    (align_hour, align_hour_null),
    (align_30min, align_30min_null),
    (align_20min, align_20min_null),
    (align_15min, align_15min_null),
    (align_midnight, align_midnight_null),
    (align_month_first, align_month_first_null),
    (align_sunday, align_sunday_null),
    (align_monday, align_monday_null),
]

IDS = [p[0].__name__ for p in PAIRS]


# ---- null variants: same result as the non-null one, None -> None ----

@pytest.mark.parametrize("fn,fn_null", PAIRS, ids=IDS)
def test_null_variant_none(fn, fn_null):
    """_null variant returns None for None"""
    assert fn_null(None) is None


@pytest.mark.parametrize("fn,fn_null", PAIRS, ids=IDS)
@pytest.mark.parametrize("dt", [
    datetime(2026, 3, 18, 9, 47, 33, 5),
    datetime(2026, 3, 18, 9, 47, 33, 5, tzinfo=timezone.utc),
    datetime(2026, 3, 18, 9, 47, 33, 5, tzinfo=EST),
], ids=["naive", "utc", "est"])
def test_null_variant_matches_non_null(fn, fn_null, dt):
    """_null variant gives the same result as the non-null one for non-None values"""
    assert fn_null(dt) == fn(dt)
    assert fn_null(dt).tzinfo == fn(dt).tzinfo


def test_align_minutes_null():
    """align_minutes_null: None -> None, otherwise same as align_minutes"""
    dt = datetime(2026, 3, 18, 9, 47, 33)
    assert align_minutes_null(None, 15) is None
    assert align_minutes_null(dt, 15) == align_minutes(dt, 15) == datetime(2026, 3, 18, 9, 45)


def test_every_function_has_null_variant():
    """Every public date function in utils has a _null twin covered here"""
    public = {n for n in dir(utils) if callable(getattr(utils, n)) and not n.startswith("_") and n != "datetime" and n != "timedelta"}
    base = {n for n in public if not n.endswith("_null")}
    assert {n + "_null" for n in base} == public - base
    covered = {f.__name__ for f, _ in PAIRS} | {"align_minutes"}
    assert base == covered


# ---- unzone ----

def test_unzone_utc_keeps_wall_clock():
    """9:00 UTC -> 9:00 naive"""
    r = unzone(datetime(2026, 1, 2, 21, 0, tzinfo=timezone.utc))
    assert r == datetime(2026, 1, 2, 21, 0)
    assert r.tzinfo is None


def test_unzone_est_keeps_wall_clock():
    """8:00 EST -> 8:00 naive (no conversion)"""
    r = unzone(datetime(2026, 1, 2, 8, 0, tzinfo=EST))
    assert r == datetime(2026, 1, 2, 8, 0)
    assert r.tzinfo is None


def test_unzone_naive_unchanged():
    d = datetime(2026, 1, 2, 3, 4, 5, 6)
    assert unzone(d) == d


# ---- align_minutes / hour / 15 / 20 / 30 ----

@pytest.mark.parametrize("minutes,expected", [
    (60, datetime(2026, 3, 18, 9, 0)),
    (30, datetime(2026, 3, 18, 9, 30)),
    (20, datetime(2026, 3, 18, 9, 40)),
    (15, datetime(2026, 3, 18, 9, 45)),
    (10, datetime(2026, 3, 18, 9, 40)),
    (5,  datetime(2026, 3, 18, 9, 45)),
    (1,  datetime(2026, 3, 18, 9, 47)),
])
def test_align_minutes(minutes, expected):
    assert align_minutes(datetime(2026, 3, 18, 9, 47, 33, 5), minutes) == expected


def test_align_minutes_zero_returns_as_is():
    """minutes=0 returns the datetime unchanged (no alignment, seconds/micros kept)"""
    d = datetime(2026, 3, 18, 9, 47, 33, 5, tzinfo=EST)
    assert align_minutes(d, 0) is d
    assert align_minutes_null(None, 0) is None


@pytest.mark.parametrize("fn,minute,expected_minute", [
    (align_hour, 0, 0), (align_hour, 59, 0),
    (align_30min, 0, 0), (align_30min, 29, 0), (align_30min, 30, 30), (align_30min, 59, 30),
    (align_20min, 0, 0), (align_20min, 19, 0), (align_20min, 20, 20), (align_20min, 39, 20), (align_20min, 40, 40), (align_20min, 59, 40),
    (align_15min, 0, 0), (align_15min, 14, 0), (align_15min, 15, 15), (align_15min, 44, 30), (align_15min, 45, 45), (align_15min, 59, 45),
])
def test_align_boundaries(fn, minute, expected_minute):
    r = fn(datetime(2026, 3, 18, 9, minute, 59, 999999))
    assert r == datetime(2026, 3, 18, 9, expected_minute, 0, 0)


@pytest.mark.parametrize("fn", [align_hour, align_30min, align_20min, align_15min])
def test_align_minutes_does_not_change_hour_or_day(fn):
    """Alignment only goes back within the hour"""
    r = fn(datetime(2026, 12, 31, 23, 59, 59, 999999))
    assert (r.year, r.month, r.day, r.hour) == (2026, 12, 31, 23)


@pytest.mark.parametrize("fn", [align_hour, align_30min, align_20min, align_15min, align_midnight, align_month_first, align_sunday, align_monday])
def test_align_keeps_tzinfo(fn):
    """tzinfo is preserved as-is and wall-clock is not converted"""
    assert fn(datetime(2026, 3, 18, 9, 47, tzinfo=EST)).tzinfo is EST
    assert fn(datetime(2026, 3, 18, 9, 47, tzinfo=timezone.utc)).tzinfo is timezone.utc
    assert fn(datetime(2026, 3, 18, 9, 47)).tzinfo is None


# ---- midnight / month ----

def test_align_midnight():
    assert align_midnight(datetime(2026, 3, 18, 9, 47, 33, 5)) == datetime(2026, 3, 18)
    assert align_midnight(datetime(2026, 3, 18)) == datetime(2026, 3, 18)
    assert align_midnight(datetime(2026, 3, 18, 23, 59, 59, 999999)) == datetime(2026, 3, 18)


def test_align_month_first():
    assert align_month_first(datetime(2026, 3, 18, 9, 47, 33, 5)) == datetime(2026, 3, 1)
    assert align_month_first(datetime(2026, 3, 1)) == datetime(2026, 3, 1)
    assert align_month_first(datetime(2026, 12, 31, 23, 59)) == datetime(2026, 12, 1)


# ---- week: 2026-03-15 is Sunday, 2026-03-16 is Monday ----

@pytest.mark.parametrize("day,expected", [
    (15, 15),  # Sunday -> itself
    (16, 15),  # Monday
    (18, 15),  # Wednesday
    (21, 15),  # Saturday
    (22, 22),  # next Sunday
])
def test_align_sunday(day, expected):
    assert align_sunday(datetime(2026, 3, day, 13, 30, 15, 7)) == datetime(2026, 3, expected)


@pytest.mark.parametrize("day,expected", [
    (15, 9),   # Sunday belongs to the week that started on previous Monday
    (16, 16),  # Monday -> itself
    (18, 16),  # Wednesday
    (22, 16),  # Sunday
    (23, 23),  # next Monday
])
def test_align_monday(day, expected):
    assert align_monday(datetime(2026, 3, day, 13, 30, 15, 7)) == datetime(2026, 3, expected)


def test_align_week_crosses_month_and_year():
    """2026-04-01 is Wednesday; 2026-01-01 is Thursday"""
    assert align_sunday(datetime(2026, 4, 1, 10)) == datetime(2026, 3, 29)
    assert align_monday(datetime(2026, 4, 1, 10)) == datetime(2026, 3, 30)
    assert align_sunday(datetime(2026, 1, 1, 10)) == datetime(2025, 12, 28)
    assert align_monday(datetime(2026, 1, 1, 10)) == datetime(2025, 12, 29)
