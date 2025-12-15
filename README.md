# MSAL Schedule to Google Calendar Sync

This tool logs into [lk.msal.ru](https://lk.msal.ru/auth) with Playwright, fetches weekly schedules, parses lessons, and syncs them into Google Calendar.

## Prerequisites
- Python 3.11+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  playwright install chromium
  ```
- Copy your Google OAuth Desktop credentials JSON to `credentials.json` (or set `GOOGLE_CLIENT_SECRETS`). Enable the Google Calendar API for your project.
- Create a `.env` file based on `.env.example`:
  ```env
  MSAL_LOGIN=your_login
  MSAL_PASSWORD=your_password
  CALENDAR_ID=primary
  TIMEZONE=Europe/Moscow
  GOOGLE_CLIENT_SECRETS=credentials.json
  GOOGLE_TOKEN_FILE=token.json
  ```

## Usage
Run in dry-run mode (no calendar changes) and headful browser (for captcha/2FA):
```bash
export MSAL_LOGIN=...
export MSAL_PASSWORD=...
python main.py --start 2025-12-15 --weeks 4 --dry-run --headful
```

Run normally (creates/updates Google Calendar events):
```bash
export MSAL_LOGIN=...
export MSAL_PASSWORD=...
python main.py --start 2025-12-15 --weeks 4
```

### Flags
- `--start YYYY-MM-DD` – first week start date (default: today)
- `--weeks N` – number of weeks to sync (default: 4)
- `--headful` – open a visible browser window for manual captcha/2FA
- `--dry-run` – log actions without changing Google Calendar
- `--delete-missing` – remove managed events no longer present in the schedule

## Notes
- Session cookies are persisted in `storage_state.json` to avoid repeated logins.
- HTML snapshots are stored in `artifacts/pages/`; screenshots can be added under `artifacts/screenshots/` if needed for debugging.
- The sync is idempotent via `source_id` hashes stored in event extended properties.
