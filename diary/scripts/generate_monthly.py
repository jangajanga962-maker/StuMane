#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate monthly diary PDF (runs daily; only executes when 2 days before the 1st)."""
import io, os, sys, calendar
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

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "template", "MUJI_Notebook_2026-2028.pdf")
FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
W, H = 841.8898, 595.2756
ACCENT = HexColor("#FF3B30")
INK = HexColor("#0a0a0a")
GRAY = HexColor("#bbbbbb")

# index3 = 2026/4（★1ずらすと別の月に描画されるので厳守）
MONTH_PAGE = {}
_y, _m = 2026, 4
for _i in range(3, 27):
    MONTH_PAGE[(_y, _m)] = _i
    _m += 1
    if _m > 12:
        _m = 1; _y += 1


def run():
    today = datetime.now(JST).date()

    # Only run when today is exactly 2 days before the 1st of next month
    if (today + timedelta(days=2)).day != 1:
        print(f"Skipping: {today} is not 2 days before the 1st of next month.")
        return None

    target = today + timedelta(days=2)
    year, month = target.year, target.month
    print(f"Generating monthly for {year}-{month:02d}")

    pdfmetrics.registerFont(TTFont("IPAG", FONT_PATH))

    notion_token = os.environ["NOTION_TOKEN"]
    apple_id = os.environ["APPLE_ID"]
    apple_password = os.environ["APPLE_APP_PASSWORD"]

    _, last_day = calendar.monthrange(year, month)
    start_dt = JST.localize(datetime(year, month, 1, 0, 0))
    # C5 fix: use first day of next month (exclusive) per RFC 4791 CalDAV
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end_dt = JST.localize(datetime(next_year, next_month, 1, 0, 0))
    events = fetch_events(apple_id, apple_password, start_dt, end_dt)

    EVENTS_BY_DATE = {}
    for ev in events:
        day = ev["start"].day
        if day not in EVENTS_BY_DATE:
            EVENTS_BY_DATE[day] = ev["title"]
        else:
            EVENTS_BY_DATE[day] += f"/{ev['title']}"

    tasks = fetch_tasks(notion_token)
    TODO = tasks["block2"] + tasks["block3"]

    pidx = MONTH_PAGE.get((year, month))
    if pidx is None:
        print(f"Month {year}/{month} is out of template range (2026/4-2028/3).")
        return None

    COL_X = {0: 192, 1: 288, 2: 384, 3: 480, 4: 576, 5: 672, 6: 768}
    ROW_Y = [459, 370, 281, 192, 103, 14]
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(year, month)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFont("IPAG", 7)
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week):
            if day == 0:
                continue
            ev = EVENTS_BY_DATE.get(day)
            if ev:
                c.setFillColor(ACCENT)
                c.drawString(COL_X[di] + 2, ROW_Y[wi] - 12, ev[:11])

    c.setFont("IPAG", 8)
    todo_y = [461, 439, 417, 395, 373, 351, 329, 307, 285, 263, 241, 219, 197, 175]
    if TODO:
        for i, t in enumerate(TODO[:14]):
            c.setFillColor(INK); c.drawString(46, todo_y[i] - 1, t[:16])
    else:
        c.setFillColor(GRAY); c.drawString(46, todo_y[0] - 1, "（DB空）")

    c.showPage(); c.save(); buf.seek(0)

    overlay = PdfReader(buf)
    base = PdfReader(TEMPLATE)
    writer = PdfWriter()
    pg = base.pages[pidx]
    pg.merge_page(overlay.pages[0])
    writer.add_page(pg)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"diary-{year}-{month:02d}-monthly.pdf")
    with open(out, "wb") as f:
        writer.write(f)
    print(f"Generated: {out}")
    return out


if __name__ == "__main__":
    run()
