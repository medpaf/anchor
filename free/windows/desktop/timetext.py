import time
from datetime import datetime, timedelta

def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")

def screen_time(ms):

    minutes = int(ms or 0) // 60_000
    if not ms or ms <= 0:
        return "Not used"
    if minutes < 1:
        return "Less than a minute"
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h" + (f" {minutes % 60} min" if minutes % 60 else "")

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

    return "all day" if start == end else f"{start}–{end}"

def clock(ms, now=None):

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

    now_dt = datetime.fromtimestamp(now if now is not None else time.time()).replace(second=0, microsecond=0)
    target = now_dt.replace(hour=hour, minute=minute)
    if target <= now_dt:
        target += timedelta(days=1)
    return int((target - now_dt).total_seconds() // 60)
