"""Filter output/events.csv down to the upcoming 7 days and write docs/data.json
for the GitHub Pages site. Run after scraper.py as part of the scheduled workflow.
"""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
EVENTS_CSV = BASE_DIR / "output" / "events.csv"
DATA_JSON = BASE_DIR / "docs" / "data.json"
WINDOW_DAYS = 7

# Matches: "9/2", "⤷ 9/2", "10/1-3" (same-month range), "10/29-11/5" (cross-month range)
DATE_RE = re.compile(
    r"^(?:⤷\s*)?(?P<sm>\d{1,2})/(?P<sd>\d{1,2})"
    r"(?:-(?:(?P<em>\d{1,2})/)?(?P<ed>\d{1,2}))?$"
)
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})\s*(am|pm)$", re.IGNORECASE)


def time_sort_key(raw: str):
    """Minutes since midnight for chronological sort; blank/unparseable times
    (TBD, all-day tournaments) sort after every timed event on the same day."""
    match = TIME_RE.match(str(raw).strip())
    if not match:
        return 24 * 60
    hour, minute, meridiem = int(match.group(1)), int(match.group(2)), match.group(3).lower()
    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute


def resolve_year(month: int, day: int, today: date) -> int:
    """Attach a year to a bare M/D value, rolling to next year if the
    resulting date would otherwise fall more than 30 days in the past
    (handles the run that happens right around a Dec -> Jan boundary)."""
    candidate = date(today.year, month, day)
    if (today - candidate).days > 30:
        candidate = date(today.year + 1, month, day)
    return candidate.year


def parse_event_date(raw: str, today: date):
    """Return (start_date, end_date) or None if unparseable."""
    match = DATE_RE.match(str(raw).strip())
    if not match:
        return None

    sm, sd = int(match.group("sm")), int(match.group("sd"))
    start_year = resolve_year(sm, sd, today)
    start = date(start_year, sm, sd)

    em, ed = match.group("em"), match.group("ed")
    if ed is None:
        end = start
    else:
        end_month = int(em) if em else sm
        end_day = int(ed)
        end_year = start_year
        if end_month < sm:
            end_year += 1
        end = date(end_year, end_month, end_day)

    return start, end


def format_display_date(start: date, end: date) -> str:
    if start == end:
        return start.strftime("%a %b %-d")
    return f"{start.strftime('%a %b %-d')}–{end.strftime('%b %-d')}"


def build():
    today = date.today()
    window_end = today + timedelta(days=WINDOW_DAYS - 1)

    df = pd.read_csv(EVENTS_CSV, dtype=str).fillna("")

    events = []
    for _, row in df.iterrows():
        parsed = parse_event_date(row["event_date"], today)
        if parsed is None:
            continue
        start, end = parsed
        if end < today or start > window_end:
            continue

        events.append(
            {
                "date": start.isoformat(),
                "display_date": format_display_date(start, end),
                "day_name": start.strftime("%A"),
                "school_name": row["school_name"],
                "activity_name": row["activity_name"],
                "event_time": row["event_time"],
                "event_name": row["event_name"],
                "location": row["location"],
                "address": row["address"],
                "score": row["score"],
            }
        )

    events.sort(key=lambda e: (e["date"], time_sort_key(e["event_time"]), e["school_name"]))

    DATA_JSON.parent.mkdir(exist_ok=True)
    with DATA_JSON.open("w") as f:
        json.dump(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "window_start": today.isoformat(),
                "window_end": window_end.isoformat(),
                "events": events,
            },
            f,
            indent=2,
        )

    print(f"Wrote {len(events)} events ({today} – {window_end}) to {DATA_JSON}")


if __name__ == "__main__":
    build()
