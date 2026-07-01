#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate next week's weekly diary PDF (runs Sunday 22:00 JST)."""
import io, os, sys
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
import pytz

sys.path.insert(0, os.path.dirname(__file__))
from fetch_notion import fetch_tasks
from fetch_calendar import fetch_events

JST = pytz.timezone("Asia/Tokyo")
WEEKDAYS_JA = ["月", "火", "水", "木", "金", "土", "日"]

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "template", "MUJI_Notebook_2026-2028.pdf")
FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
W, H = 841.8898, 595.2756
ACCENT = HexColor("#FF3B30")
INK = HexColor("#0a0a0a")
GRAY = HexColor("#bbbbbb")


def week_of_month(d) -> int:
    """1-based week number within the month (Monday-based)."""
    first = d.replace(day=1)
    first_monday = first - timedelta(days=first.weekday())
    return (d - first_monday).days // 7 + 1


def run():
    pdfmetrics.registerFont(TTFont("IPAG", FONT_PATH))

    today = datetime.now(JST).date()
    # Next Monday (tomorrow if today is Sunday)
    days_ahead = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_ahead)
    next_sunday = next_monday + timedelta(days=6)

    year = next_monday.year
    month = next_monday.month
    week_no = week_of_month(next_monday)
    span = f"{next_monday.month}/{next_monday.day}-{next_sunday.month}/{next_sunday.day}"

    notion_token = os.environ["NOTION_TOKEN"]
    apple_id = os.environ["APPLE_ID"]
    apple_password = os.environ["APPLE_APP_PASSWORD"]

    start_dt = JST.localize(datetime(next_monday.year, next_monday.month, next_monday.day, 0, 0))
    # C5 fix: use midnight of next day (exclusive) per RFC 4791 CalDAV
    end_dt = JST.localize(datetime(next_sunday.year, next_sunday.month, next_sunday.day)) + timedelta(days=1)
    events = fetch_events(apple_id, apple_password, start_dt, end_dt)

    EVENTS_BY_DAY = {}
    for ev in events:
        wd = WEEKDAYS_JA[ev["start"].weekday()]
        if ev["all_day"]:
            EVENTS_BY_DAY.setdefault(wd, []).append(ev["title"])
        else:
            t = f"{ev['start'].hour:02d}:{ev['start'].minute:02d} {ev['title']}"
            if ev["location"]:
                t += f" @{ev['location']}"
            EVENTS_BY_DAY.setdefault(wd, []).append(t)

    tasks = fetch_tasks(notion_token)
    ZONE_B = tasks["block2"] + tasks["block3"]

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFont("IPAG", 10); c.setFillColor(INK)
    c.drawString(300, 525, str(year))
    c.drawString(372, 525, str(month))
    c.drawString(440, 525, str(week_no))
    c.drawString(512, 525, span)

    c.setFont("IPAG", 8.5)
    zb_y = [463, 441, 419, 397, 375, 353, 331, 309, 287, 265, 243, 221]
    if ZONE_B:
        for i, t in enumerate(ZONE_B[:12]):
            c.setFillColor(INK); c.drawString(345, zb_y[i] - 1, t[:34])
    else:
        c.setFillColor(GRAY); c.drawString(345, zb_y[0] - 1, "（タスク総括DBが空のため未記入）")

    c.setFont("IPAG", 7.5)
    ax, ay = 28, 470
    for wd in WEEKDAYS_JA:
        evs = EVENTS_BY_DAY.get(wd, [])
        if not evs:
            continue
        c.setFillColor(ACCENT); c.drawString(ax, ay, wd)
        c.setFillColor(INK)
        for e in evs:
            c.drawString(ax + 18, ay, e[:30]); ay -= 12
        ay -= 4
        if ay < 150:
            break

    c.showPage(); c.save(); buf.seek(0)

    overlay = PdfReader(buf)
    base = PdfReader(TEMPLATE)
    writer = PdfWriter()
    pg = base.pages[2]
    pg.merge_page(overlay.pages[0])
    writer.add_page(pg)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"diary-{year}-{month:02d}-week-{week_no}-weekly.pdf")
    with open(out, "wb") as f:
        writer.write(f)
    print(f"Generated: {out}")
    return out


if __name__ == "__main__":
    run()
