"""
General purpose utilities for Azos framework.

Copyright (C) 2020, 2026 Azist, MIT License

"""

from datetime import datetime, timedelta

#region Dates/Time
def unzone(dt: datetime) -> datetime:
    """
    Drops time zone info from a datetime WITHOUT converting the wall-clock time,
    e.g. 9:00 UTC -> 9:00 naive, 8:00 EST -> 8:00 naive
    """
    return dt.replace(tzinfo=None)

def unzone_null(dt: datetime | None) -> datetime | None:
    """
    Drops time zone info from a datetime WITHOUT converting the wall-clock time,
    e.g. 9:00 UTC -> 9:00 naive, 8:00 EST -> 8:00 naive. `None` returns `None`.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=None)



def align_minutes(dt: datetime, minutes: int) -> datetime:
    """
    Aligns (rounds down) to the nearest preceding boundary of `minutes` within the hour, zeroing seconds and
    microseconds and keeping time zone info as-is, e.g. `minutes=15` turns 9:47:33 into 9:45:00.
    `minutes` must be a positive int, typically a divisor of 60 (use 60 to align to the hour).
    `minutes=0` returns `dt` unchanged.
    """
    if minutes == 0:
        return dt
    return dt.replace(minute=dt.minute - dt.minute % minutes, second=0, microsecond=0)

def align_minutes_null(dt: datetime | None, minutes: int) -> datetime | None:
    """Null-tolerant `align_minutes()`: returns `None` for `None`."""
    return None if dt is None else align_minutes(dt, minutes)

def align_hour(dt: datetime) -> datetime:
    """Aligns (rounds down) to the start of the hour (mm:ss.ffffff zeroed), keeping its time zone info as-is."""
    return align_minutes(dt, 60)

def align_hour_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_hour()`: returns `None` for `None`."""
    return None if dt is None else align_hour(dt)

def align_30min(dt: datetime) -> datetime:
    """Aligns (rounds down) to the 30-minute boundary (:00, :30), keeping its time zone info as-is."""
    return align_minutes(dt, 30)

def align_30min_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_30min()`: returns `None` for `None`."""
    return None if dt is None else align_30min(dt)

def align_20min(dt: datetime) -> datetime:
    """Aligns (rounds down) to the 20-minute boundary (:00, :20, :40), keeping its time zone info as-is."""
    return align_minutes(dt, 20)

def align_20min_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_20min()`: returns `None` for `None`."""
    return None if dt is None else align_20min(dt)

def align_15min(dt: datetime) -> datetime:
    """Aligns (rounds down) to the 15-minute boundary (:00, :15, :30, :45), keeping its time zone info as-is."""
    return align_minutes(dt, 15)

def align_15min_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_15min()`: returns `None` for `None`."""
    return None if dt is None else align_15min(dt)

def align_midnight(dt: datetime) -> datetime:
    """Returns the start of the day (00:00:00.000000) for the datetime, keeping its time zone info as-is."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def align_midnight_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_midnight()`: returns `None` for `None`."""
    return None if dt is None else align_midnight(dt)

def align_month_first(dt: datetime) -> datetime:
    """Returns the first day of the datetime's month at align_midnight (00:00:00.000000), keeping its time zone info as-is."""
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

def align_month_first_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_month_first()`: returns `None` for `None`."""
    return None if dt is None else align_month_first(dt)

def align_sunday(dt: datetime) -> datetime:
    """Returns align_midnight of the Sunday that starts the datetime's week (the datetime's own day if it is a Sunday), keeping its time zone info as-is."""
    return (dt - timedelta(days=(dt.weekday() + 1) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)

def align_sunday_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_sunday()`: returns `None` for `None`."""
    return None if dt is None else align_sunday(dt)

def align_monday(dt: datetime) -> datetime:
    """Returns align_midnight of the Monday that starts the datetime's week (the datetime's own day if it is a Monday), keeping its time zone info as-is."""
    return (dt - timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

def align_monday_null(dt: datetime | None) -> datetime | None:
    """Null-tolerant `align_monday()`: returns `None` for `None`."""
    return None if dt is None else align_monday(dt)

#endregion

#region Strings


#endregion




