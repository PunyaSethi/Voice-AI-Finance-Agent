from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_amount(value: Any) -> float:
    if value is None:
        raise ValueError("amount is required")

    raw_value = str(value).strip().lower()
    raw_value = raw_value.replace(",", "")
    raw_value = re.sub(r"^(rs\.?|inr|₹|\$)\s*", "", raw_value)

    multiplier = Decimal("1")
    if raw_value.endswith("k"):
        multiplier = Decimal("1000")
        raw_value = raw_value[:-1]
    elif raw_value.endswith(("lakh", "lakhs")):
        multiplier = Decimal("100000")
        raw_value = re.sub(r"\s*lakhs?$", "", raw_value)

    try:
        amount = Decimal(raw_value) * multiplier
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be a valid number") from exc

    if amount <= 0:
        raise ValueError("amount must be greater than zero")
    return float(amount)


def compact_text(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def parse_period(text: str, now: datetime | None = None) -> dict[str, str] | None:
    query = text.lower()
    today = (now or datetime.now()).date()

    if "last week" in query:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=7)
        return _period_dict(start, end)

    if "this week" in query:
        start = today - timedelta(days=today.weekday())
        return _period_dict(start, today + timedelta(days=1))

    if "last month" in query:
        first_this_month = today.replace(day=1)
        last_previous_month = first_this_month - timedelta(days=1)
        start = last_previous_month.replace(day=1)
        return _period_dict(start, first_this_month)

    if "this month" in query:
        start = today.replace(day=1)
        return _period_dict(start, today + timedelta(days=1))

    if "today" in query:
        return _period_dict(today, today + timedelta(days=1))

    if "yesterday" in query:
        start = today - timedelta(days=1)
        return _period_dict(start, today)

    return None


def parse_due_time(text: str, now: datetime | None = None) -> str | None:
    query = text.lower()
    current = now or datetime.now()
    due_date = current.date()

    if "tomorrow" in query:
        due_date = due_date + timedelta(days=1)
    elif "next week" in query:
        due_date = due_date + timedelta(days=7)
    elif "today" not in query:
        return None

    due_time = time(hour=9)
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", query)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            due_time = time(hour=hour, minute=minute)

    return datetime.combine(due_date, due_time).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _period_dict(start: date, end: date) -> dict[str, str]:
    return {
        "start_date": datetime.combine(start, time.min).isoformat(),
        "end_date": datetime.combine(end, time.min).isoformat(),
    }
