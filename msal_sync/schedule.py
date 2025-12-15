from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

from playwright.sync_api import Page

from .models import Event
from .parser import ParseError, parse_events_from_html

BASE_URL = "https://lk.msal.ru/schedule"


def fetch_schedule_for_week(page: Page, from_date: date, to_date: date, tz: ZoneInfo) -> List[Event]:
    url = f"{BASE_URL}?from={from_date.isoformat()}&to={to_date.isoformat()}"
    logging.info("Fetching schedule %s", url)
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(500)
    page.wait_for_selector("div.days-schedule", timeout=10_000)
    html = page.content()

    pages_dir = Path("artifacts/pages")
    pages_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = pages_dir / f"{from_date.isoformat()}_{to_date.isoformat()}.html"
    artifact_path.write_text(html, encoding="utf-8")

    try:
        events = parse_events_from_html(html, tz)
    except ParseError as exc:
        logging.error("Failed to parse schedule for %s-%s: %s", from_date, to_date, exc)
        screenshots_dir = Path("artifacts/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshots_dir / f"{from_date.isoformat()}_{to_date.isoformat()}.png"
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
            logging.info("Saved screenshot to %s", screenshot_path)
        except Exception as shot_exc:
            logging.warning("Unable to capture screenshot: %s", shot_exc)
        raise

    logging.info("Parsed %d events for %s - %s", len(events), from_date, to_date)
    return events
