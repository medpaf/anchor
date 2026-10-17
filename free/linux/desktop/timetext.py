"""Human-friendly times and days for the UI."""

import time
from datetime import datetime, timedelta


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def days_text(days):
    days = sorted(set(days))
    if days == [1, 2, 3, 4, 5, 6, 7]:
        return "Every day"
    if days == [1, 2, 3, 4, 5]:
        return "Weekdays"
    if days == [6, 7]:
        return "Weekends"
    return ", ".join(DAY_NAMES[d - 1] for d in days)


def hours_text(start, end):
    """'22:30–07:00', or 'all day' for a 24-hour window."""
    return "all day" if start == end else f"{start}–{end}"


def clock(ms, now=None):
    """'18:00', or 'Tue 07:00' when it isn't today."""
    t = datetime.fromtimestamp(ms / 1000)
    today = datetime.fromtimestamp(now if now is not None else time.time()).date()
    return t.strftime("%H:%M") if t.date() == today else t.strftime("%a %H:%M")


def countdown(ms, now=None):
    minutes = max(0, round((ms / 1000 - (now if now is not None else time.time())) / 60))
    if minutes < 60:
        return f"in {plural(minutes, 'minute')}"
    h, m = divmod(minutes, 60)
    return f"in {h} h {m} min" if m else f"in {plural(h, 'hour')}"


def minutes_until(hour, minute, now=None):
    """Minutes from now until the next hh:mm (today, or tomorrow if that time has passed)."""
    now_dt = datetime.fromtimestamp(now if now is not None else time.time()).replace(second=0, microsecond=0)
    target = now_dt.replace(hour=hour, minute=minute)
    if target <= now_dt:
        target += timedelta(days=1)
    return int((target - now_dt).total_seconds() // 60)
