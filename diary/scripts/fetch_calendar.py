#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import caldav
from icalendar import Calendar
from datetime import datetime, date, timedelta
import pytz

JST = pytz.timezone("Asia/Tokyo")


def fetch_events(apple_id: str, app_password: str,
                 start_dt: datetime, end_dt: datetime) -> list:
    """Fetch events from iCloud Calendar via CalDAV.

    start_dt / end_dt must be timezone-aware datetimes (JST recommended).
    Returns list of dicts: {title, location, start, end, all_day}.
    """
    client = caldav.DAVClient(
        url="https://caldav.icloud.com",
        username=apple_id,
        password=app_password,
    )

    try:
        principal = client.principal()
        calendars = principal.calendars()
    except Exception as e:
        # C4 fix: surface connection errors so the workflow fails instead of writing a blank PDF
        raise RuntimeError(f"CalDAV connection failed: {e}") from e

    events = []
    failed_cals = []
    for cal in calendars:
        try:
            results = cal.date_search(start=start_dt, end=end_dt, expand=True)
        except Exception as e:
            # C10 fix: track per-calendar failures rather than swallowing them silently
            failed_cals.append((str(cal), str(e)))
            continue

        for ev_obj in results:
            try:
                ical = Calendar.from_ical(ev_obj.data)
                for component in ical.walk():
                    if component.name != "VEVENT":
                        continue

                    dtstart_raw = component.get("DTSTART")
                    if dtstart_raw is None:
                        continue
                    dtstart = dtstart_raw.dt

                    dtend_raw = component.get("DTEND")
                    dtend = dtend_raw.dt if dtend_raw else None

                    summary = str(component.get("SUMMARY", ""))
                    location = str(component.get("LOCATION", ""))

                    all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)

                    # Normalise to JST datetime
                    if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
                        dtstart = JST.localize(datetime(dtstart.year, dtstart.month, dtstart.day))
                    elif dtstart.tzinfo is None:
                        dtstart = JST.localize(dtstart)
                    else:
                        dtstart = dtstart.astimezone(JST)

                    if dtend is not None:
                        if isinstance(dtend, date) and not isinstance(dtend, datetime):
                            # C6 fix: RFC 5545 all-day DTEND is exclusive; subtract 1 day
                            dtend_adj = dtend - timedelta(days=1)
                            dtend = JST.localize(datetime(dtend_adj.year, dtend_adj.month, dtend_adj.day))
                        elif dtend.tzinfo is None:
                            dtend = JST.localize(dtend)
                        else:
                            dtend = dtend.astimezone(JST)

                    events.append({
                        "title": summary,
                        "location": location,
                        "start": dtstart,
                        "end": dtend,
                        "all_day": all_day,
                    })
            except Exception as e:
                print(f"Warning: could not parse event: {e}")

    if failed_cals:
        print(f"WARNING: {len(failed_cals)} calendar(s) failed to fetch:")
        for cal_name, err in failed_cals:
            print(f"  - {cal_name}: {err}")

    events.sort(key=lambda e: e["start"])
    return events
