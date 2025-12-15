from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .config import Settings

LOGIN_URL = "https://lk.msal.ru/auth"


def _find_first(page: Page, selectors: list[str]) -> Optional[str]:
    for selector in selectors:
        el = page.query_selector(selector)
        if el:
            return selector
    return None


def create_context(settings: Settings, headful: bool = False) -> Tuple[Playwright, Browser, BrowserContext]:
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=not headful)
    storage_state = Path(settings.storage_state_path)
    context = browser.new_context(storage_state=str(storage_state) if storage_state.exists() else None)
    return playwright, browser, context


def ensure_login(settings: Settings, headful: bool = False) -> tuple[Playwright, Browser, BrowserContext, Page]:
    playwright, browser, context = create_context(settings, headful=headful)
    page = context.new_page()
    page.goto(LOGIN_URL)

    if page.url.startswith(LOGIN_URL):
        logging.info("Attempting interactive login...")
        login_selector = _find_first(
            page,
            [
                "input[name*='login' i]",
                "input[name*='user' i]",
                "input[type='email']",
                "input[type='text']",
            ],
        )
        password_selector = _find_first(page, ["input[type='password']"])
        if not login_selector or not password_selector:
            raise RuntimeError("Unable to locate login form fields")

        page.fill(login_selector, settings.msal_login)
        page.fill(password_selector, settings.msal_password)

        submit = page.query_selector("button[type='submit']")
        if submit:
            submit.click()
        else:
            page.press(password_selector, "Enter")

        page.wait_for_timeout(1000)
        page.wait_for_load_state("networkidle")

    try:
        page.goto("https://lk.msal.ru/schedule", wait_until="networkidle")
    except Exception:
        logging.error("Navigation to schedule failed; captcha or 2FA may be required")
        context.storage_state(path=settings.storage_state_path)
        raise

    if page.url.startswith(LOGIN_URL):
        logging.error("Still on login page; manual intervention may be required")
        context.storage_state(path=settings.storage_state_path)
        raise RuntimeError("Login failed, captcha/2FA may be required")

    logging.info("Login successful, session stored at %s", settings.storage_state_path)
    context.storage_state(path=settings.storage_state_path)
    return playwright, browser, context, page
