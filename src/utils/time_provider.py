"""
Centralized time utilities with timezone awareness.
Defaults to the user's local timezone (Houston, US Central).
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from config import config


def _tz() -> ZoneInfo:
    tz_name = getattr(config, "TIMEZONE", "America/Chicago")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        # Fallback to US Central if misconfigured
        return ZoneInfo("America/Chicago")


def now() -> datetime:
    """Current localized datetime with timezone awareness."""
    return datetime.now(_tz())


def today_str() -> str:
    """Today's date in YYYY-MM-DD for prompts and logs."""
    return now().strftime("%Y-%m-%d")


def current_year() -> int:
    return now().year


def month_year_label() -> str:
    """Human-friendly label like 'August 2025'."""
    return now().strftime("%B %Y")


def iso_timestamp() -> str:
    """ISO-8601 timestamp with timezone offset."""
    return now().isoformat()
