from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from msal_sync.browser import ensure_login
from msal_sync.config import get_settings
from msal_sync.gcal import build_service, sync_events
from msal_sync.schedule import fetch_schedule_for_week


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync MSAL schedule to Google Calendar")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD", default=None)
    parser.add_argument("--weeks", type=int, default=4, help="Number of weeks to sync")
    parser.add_argument("--headful", action="store_true", help="Open browser headful for captcha/2FA")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without modifying calendar")
    parser.add_argument("--delete-missing", action="store_true", help="Delete events missing from schedule")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    settings = get_settings()
    tz = settings.timezone

    if args.start:
        start_date = date.fromisoformat(args.start)
    else:
        start_date = datetime.now(tz).date()

    Path("artifacts/pages").mkdir(parents=True, exist_ok=True)
    Path("artifacts/screenshots").mkdir(parents=True, exist_ok=True)

    playwright, browser, context, page = ensure_login(settings, headful=args.headful)

    all_events = []
    try:
        for i in range(args.weeks):
            from_date = start_date + timedelta(days=7 * i)
            to_date = from_date + timedelta(days=6)
            events = fetch_schedule_for_week(page, from_date, to_date, tz)
            all_events.extend(events)
    finally:
        context.storage_state(path=settings.storage_state_path)
        context.close()
        browser.close()
        playwright.stop()

    if not all_events:
        logging.warning("No events parsed; nothing to sync")
        return 0

    service = build_service(settings.google_client_secrets, settings.google_token_file)
    time_min = datetime.combine(start_date, datetime.min.time(), tzinfo=tz)
    time_max = datetime.combine(start_date + timedelta(days=args.weeks * 7), datetime.max.time(), tzinfo=tz)

    sync_events(
        service=service,
        calendar_id=settings.calendar_id,
        parsed_events=all_events,
        time_min=time_min,
        time_max=time_max,
        dry_run=args.dry_run,
        delete_missing=args.delete_missing,
    )

    logging.info("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
