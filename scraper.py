import os, json, re
from datetime import datetime, timedelta
from ics import Calendar, Event
from playwright.sync_api import sync_playwright

LOGIN = os.environ["UNI_LOGIN"]
PASSWORD = os.environ["UNI_PASSWORD"]
LOGIN_URL = os.environ["LOGIN_URL"]
BASE_URL = os.environ["BASE_SCHEDULE_URL"]
TZ_NAME = os.environ.get("TZ_NAME", "Europe/Moscow")
WEEKS_AHEAD = int(os.environ.get("WEEKS_AHEAD", "16"))

def monday_of(date):
    return date - timedelta(days=date.weekday())

def fmt(d):  # YYYY-MM-DD
    return d.strftime("%Y-%m-%d")

def to_dt(date_str, time_str):
    # date_str: "YYYY-MM-DD", time_str: "HH:MM"
    return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

# Небольшой «адаптер» под любой JSON: берём первое попавшееся поле из набора синонимов
def pick(d, names):
    for n in names:
        if n in d and d[n]: return d[n]
    return None

TITLE_KEYS  = ["title","subject","discipline","name"]
START_KEYS  = ["start","startTime","timeStart","begin"]
END_KEYS    = ["end","endTime","timeEnd","finish"]
DATE_KEYS   = ["date","day","dateISO","dateUtc","dateLocal"]
ROOM_KEYS   = ["room","auditory","aud","location"]
TEACH_KEYS  = ["teacher","lecturer","professor","prepod","teacherFio","lecturerFio"]

def flatten_events(payload):
    """Находит в JSON объекты занятий c датой + временем начала/конца."""
    out = []
    def walk(x, ctx_date=None):
        if isinstance(x, dict):
            # попытка взять дату из этого уровня или контекста
            date = pick(x, DATE_KEYS) or ctx_date
            # нормализуем дату вроде "2025-09-01"
            if isinstance(date, str):
                m = re.search(r"(\d{4}-\d{2}-\d{2})", date)
                if m: date = m.group(1)
            start = pick(x, START_KEYS); end = pick(x, END_KEYS)
            if date and start and end and re.match(r"\d{1,2}:\d{2}", start) and re.match(r"\d{1,2}:\d{2}", end):
                title = pick(x, TITLE_KEYS) or "Занятие"
                room  = pick(x, ROOM_KEYS)
                teach = pick(x, TEACH_KEYS)
                desc  = " · ".join([s for s in [teach, room] if s])
                out.append({"date": date, "start": start, "end": end, "title": title, "desc": desc})
            # обход вложенностей
            for v in x.values(): walk(v, ctx_date=date)
        elif isinstance(x, list):
            for v in x: walk(v, ctx_date=ctx_date)
    walk(payload)
    return out

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(locale="ru-RU", timezone_id=TZ_NAME)
    page = context.new_page()

    # 1) Логин в ЛК (селекторы могут отличаться — при необходимости поправьте)
    page.goto(LOGIN_URL)
    page.wait_for_load_state("domcontentloaded")
    page.fill("input[name='login'], #login, input[name='username']", LOGIN)
    page.fill("input[type='password'], #password", PASSWORD)
    page.click("button:has-text('Войти'), input[type='submit']")
    page.wait_for_load_state("networkidle")

    # Достаём ACCESS_TOKEN из cookies (он нужен для Authorization: Bearer …)
    cookies = context.cookies("https://lk.msal.ru")
    access = next((c["value"] for c in cookies if c["name"].upper()=="ACCESS_TOKEN"), None)
    headers = {"Accept": "application/json"}
    if access: headers["Authorization"] = f"Bearer {access}"

    # 2) Идём неделя за неделей и копим JSON
    today = datetime.now()
    start = monday_of(today)
    weeks = [start + timedelta(days=7*i) for i in range(WEEKS_AHEAD)]

    all_items = []
    for monday in weeks:
        week_from = fmt(monday)
        week_to   = fmt(monday + timedelta(days=6))
        url = f"{BASE_URL}?from={week_from}&to={week_to}"
        resp = page.request.get(url, headers=headers)  # общий cookie-контекст от браузера
        if resp.ok:
            data = resp.json()
            all_items.extend(flatten_events(data))
        else:
            print("WARN:", url, resp.status())

    # 3) Сборка ICS
    cal = Calendar()
    seen = set()
    for it in all_items:
        key = (it["date"], it["start"], it["end"], it["title"])
        if key in seen: continue
        seen.add(key)
        ev = Event()
        ev.name = it["title"]
        ev.begin = to_dt(it["date"], it["start"])
        ev.end   = to_dt(it["date"], it["end"])
        if it["desc"]: ev.description = it["desc"]
        cal.events.add(ev)

    with open("schedule.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
