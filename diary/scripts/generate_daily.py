#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate today's daily diary PDF and save to diary/output/."""
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

TIME_Y = {
    6: 475, 7: 450, 8: 425, 9: 400, 10: 375, 11: 350, 12: 326,
    13: 301, 14: 276, 15: 251, 16: 226, 17: 201, 18: 176,
    19: 151, 20: 126, 21: 101, 22: 76, 23: 51,
}
ROW_H = 25


def y_at(hh, mm):
    if hh < 6: hh = 6
    if hh > 23: hh, mm = 23, 0
    base = TIME_Y[hh]
    nxt = TIME_Y.get(hh + 1, base - ROW_H)
    return base - (mm / 60.0) * (base - nxt)


def arrow(c, x, y, up=True):
    s = 2.4
    if up:
        c.line(x, y, x - s, y - s); c.line(x, y, x + s, y - s)
    else:
        c.line(x, y, x - s, y + s); c.line(x, y, x + s, y + s)


def run():
    pdfmetrics.registerFont(TTFont("IPAG", FONT_PATH))

    today = datetime.now(JST).date()
    notion_token = os.environ["NOTION_TOKEN"]
    apple_id = os.environ["APPLE_ID"]
    apple_password = os.environ["APPLE_APP_PASSWORD"]

    start_dt = JST.localize(datetime(today.year, today.month, today.day, 0, 0))
    end_dt = start_dt + timedelta(days=1)
    events = fetch_events(apple_id, apple_password, start_dt, end_dt)

    TIMED, ALLDAY = [], []
    for ev in events:
        if ev["all_day"]:
            ALLDAY.append(ev["title"])
        else:
            s, e = ev["start"], ev["end"]
            title = ev["title"] + (f" @{ev['location']}" if ev["location"] else "")
            # C1 fix: DTEND can be absent in some iCal events; default to 1-hour duration
            eh, em = (e.hour, e.minute) if e is not None else ((s.hour + 1) % 24, 0)
            TIMED.append((s.hour, s.minute, eh, em, title))

    tasks = fetch_tasks(notion_token, today)
    BLOCK2, BLOCK3 = tasks["block2"], tasks["block3"]

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setFont("IPAG", 11)
    c.setFillColor(INK)
    c.drawString(108, 526, str(today.year))
    c.drawString(180, 526, str(today.month))
    c.drawString(250, 526, str(today.day))
    c.drawString(300, 526, WEEKDAYS_JA[today.weekday()])

    BAR_X, LABEL_X = 64, 70
    for sh, sm, eh, em, title in TIMED:
        ys, ye = y_at(sh, sm), y_at(eh, em)
        c.setStrokeColor(ACCENT); c.setLineWidth(1.6)
        c.line(BAR_X, ys + 4, BAR_X, ye + 4)
        c.setLineWidth(1.1)
        arrow(c, BAR_X, ys + 4, True); arrow(c, BAR_X, ye + 4, False)
        name = title.split(" @")[0]
        c.setFont("IPAG", 6); c.setFillColor(ACCENT)
        midy = (ys + ye) / 2 + 2
        if len(name) > 7:
            c.drawString(LABEL_X, midy + 4, name[:7])
            c.drawString(LABEL_X, midy - 4, name[7:14])
        else:
            c.drawString(LABEL_X, midy, name[:7])

    c.setFillColor(INK); c.setFont("IPAG", 8)
    by = 470
    if BLOCK2:
        for t in BLOCK2:
            c.drawString(268, by, t[:28]); by -= 22
    else:
        c.setFillColor(HexColor("#bbbbbb"))
        c.drawString(268, by, "（タスク総括DBが空のため未記入）")

    c.setFillColor(INK); c.setFont("IPAG", 8)
    b3y = 162
    for t in BLOCK3:
        c.drawString(268, b3y, t[:28]); b3y -= 22

    if ALLDAY:
        c.setFillColor(INK); c.setFont("IPAG", 8)
        my = 345
        for t in ALLDAY:
            c.drawString(615, my, t[:24]); my -= 12

    c.showPage(); c.save(); buf.seek(0)

    overlay = PdfReader(buf)
    base = PdfReader(TEMPLATE)
    writer = PdfWriter()
    page = base.pages[1]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"diary-{today.year}-{today.month:02d}-{today.day:02d}-daily.pdf")
    with open(out, "wb") as f:
        writer.write(f)
    print(f"Generated: {out}")
    return out


if __name__ == "__main__":
    run()
