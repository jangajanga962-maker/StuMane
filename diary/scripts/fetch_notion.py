#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from datetime import date

NOTION_VERSION = "2022-06-28"
DATABASE_ID = "f6ccdaa7-0c50-4f33-9a1c-31dd3819054e"
BASE_URL = "https://api.notion.com/v1"


def fetch_tasks(token: str, target_date: date = None) -> dict:
    """Fetch active tasks from タスク総括DB.

    If target_date is given, returns only tasks where 対応予定日 == target_date
    OR 締切 <= target_date (past-due). If None, returns all non-完了 tasks.
    Returns {"block2": [...], "block3": [...]} where block2=本来, block3=頼まれ.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }

    payload = {
        "filter": {
            "property": "ステータス",
            "status": {"does_not_equal": "完了"},
        }
    }

    url = f"{BASE_URL}/databases/{DATABASE_ID}/query"

    # C2 fix: paginate through all results
    all_results = []
    cursor = None
    while True:
        paged = dict(payload)
        if cursor:
            paged["start_cursor"] = cursor
        resp = requests.post(url, headers=headers, json=paged, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        all_results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    block2 = []
    block3 = []
    target_str = target_date.isoformat() if target_date else None

    for page in all_results:
        props = page.get("properties", {})

        title = "".join(
            t.get("plain_text", "")
            for t in props.get("タスク名", {}).get("title", [])
        )
        if not title:
            continue

        if target_str:
            scheduled = (props.get("対応予定日") or {}).get("date") or {}
            deadline = (props.get("締切") or {}).get("date") or {}
            sched_start = (scheduled.get("start") or "")[:10]
            dead_start = (deadline.get("start") or "")[:10]

            if sched_start == target_str:
                pass  # include
            elif dead_start and dead_start == target_str:
                pass  # past-due
            else:
                continue

        type_sel = (props.get("種類") or {}).get("select") or {}
        if type_sel.get("name") == "頼まれ":
            block3.append(title)
        else:
            block2.append(title)

    return {"block2": block2, "block3": block3}
