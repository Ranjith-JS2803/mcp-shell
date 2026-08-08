"""Parses a period string into an inclusive [start, end) date range.

Supported formats:
  "2025"       -> whole year
  "2025-Q4"    -> quarter
  "2025-11"    -> month
  None         -> no filtering (all time)
"""

from datetime import date


def parse_period(period: str | None) -> tuple[str, str] | None:
    """Returns None (no date filter) for anything it can't parse — a
    malformed period (e.g. an LLM passing "this quarter" instead of
    "2026-Q3") should degrade to "show all time", not crash the request."""
    if not period:
        return None

    try:
        if "-Q" in period:
            year_str, quarter_str = period.split("-Q")
            year, quarter = int(year_str), int(quarter_str)
            if not 1 <= quarter <= 4:
                return None
            start_month = (quarter - 1) * 3 + 1
            start = date(year, start_month, 1)
            end_year, end_month = (year + 1, 1) if start_month == 10 else (year, start_month + 3)
            end = date(end_year, end_month, 1)
            return start.isoformat(), end.isoformat()

        if "-" in period:
            year, month = map(int, period.split("-"))
            start = date(year, month, 1)
            end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
            end = date(end_year, end_month, 1)
            return start.isoformat(), end.isoformat()

        year = int(period)
        return date(year, 1, 1).isoformat(), date(year + 1, 1, 1).isoformat()
    except (ValueError, TypeError):
        return None
