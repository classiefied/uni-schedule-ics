from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    msal_login: str
    msal_password: str
    calendar_id: str
    timezone: ZoneInfo
    google_client_secrets: str
    google_token_file: str
    storage_state_path: str = "storage_state.json"


MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


def get_timezone() -> ZoneInfo:
    tz_name = os.getenv("TIMEZONE", "Europe/Moscow")
    try:
        return ZoneInfo(tz_name)
    except Exception:  # pragma: no cover - defensive fallback
        logging.warning("Invalid TIMEZONE %s, falling back to Europe/Moscow", tz_name)
        return ZoneInfo("Europe/Moscow")


def get_settings() -> Settings:
    timezone = get_timezone()
    settings = Settings(
        msal_login=os.getenv("MSAL_LOGIN", ""),
        msal_password=os.getenv("MSAL_PASSWORD", ""),
        calendar_id=os.getenv("CALENDAR_ID", "primary"),
        timezone=timezone,
        google_client_secrets=os.getenv("GOOGLE_CLIENT_SECRETS", "credentials.json"),
        google_token_file=os.getenv("GOOGLE_TOKEN_FILE", "token.json"),
    )
    if not settings.msal_login:
        logging.warning("MSAL_LOGIN is not set")
    if not settings.msal_password:
        logging.warning("MSAL_PASSWORD is not set")
    return settings


def daterange_weeks(start: date, weeks: int) -> list[tuple[date, date]]:
    windows: list[tuple[date, date]] = []
    for i in range(weeks):
        from_date = start + timedelta(days=7 * i)
        to_date = from_date + timedelta(days=6)
        windows.append((from_date, to_date))
    return windows
