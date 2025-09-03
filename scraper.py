import os, re, math
from datetime import datetime, timedelta, timezone
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

def parse_week(page):
    """Парсит текущую страницу расписания. 
    ⚠️ Универсальная эвристика: ищем карточки с двумя временами HH:MM."""
    cards = page.query_selector_all("div, article, li")
    items = []
    for el in cards:
        text = (el.inner_text() or "").strip()
        times = re.findall(r"\b(\d{1,2}:\d{2})\b", text)
        # фильтруем только «карточки», где есть ровно два времени
        if len(times) >= 2:
            # заголовок пары: берем первую жирную/крупную строку, иначе первую строку текста
            title_el = el.query_selector("h1,h2,h3,.title,.subject,b,strong")
            title = (title_el.inner_text().strip() if title_el else text.splitlines()[0])[:120]
            # ближайшая дата — ищем вверх по DOM атрибуты с датой или подписи колонки
            date_attr = el.evaluate("""
                (node) => {
                  let p = node;
                  while (p) {
                    const ds = p.getAttribute && (p.getAttribute('data-date') || p.getAttribute('aria-label'));
                    if (ds) return ds;
                    p = p.parentElement;
                  }
                  return null;
                }
            """)
            # если дата не найдена — пропускаем (такие элементы бывают в шапке)
            if not date_attr:
                continue
            # грубый парс русской даты: «понедельник 01 сентября 2025»
            m = re.search(r"(\d{1,2}).*?(янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек).*?(\d{4})", date_attr, re.I)
            if not m:
                # fallback: иногда дата в формате 2025-09-01
                m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_attr)
                if not m2: 
                    continue
                y, mm, dd = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
            else:
                MONTHS = {"янв":1,"фев":2,"мар":3,"апр":4,"мая":5,"июн":6,"июл":7,"авг":8,"сен":9,"окт":10,"ноя":11,"дек":12}
                dd = int(m.group(1)); y = int(m.group(3)); mm = MONTHS[m.group(2).lower()[:3]]
            date = datetime(y, mm, dd)

            start, end = times[0], times[1]
            # описание: преподаватель/аудитория (ищем типичные классы)
            teacher = el.query_selector(".teacher, .lecturer")
            room = el.query_selector(".room, .aud, .location")
            desc_parts = []
            if teacher: desc_parts.append(teacher.inner_text().strip())
            if room:    desc_parts.append(room.inner_text().strip())
            items.append({
                "title": title,
                "date": date,
                "start": start,
                "end": end,
                "desc": " · ".join(desc_parts)
            })
    return items

def dt_local(date, hhmm, tz="Europe/Moscow"):
    hh, mm = map(int, hhmm.split(":"))
    return datetime(date.year, date.month, date.day, hh, mm)

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(locale="ru-RU", timezone_id=TZ_NAME)
    page = context.new_page()

    # вход в кабинет
    page.goto(LOGIN_URL)
    page.wait_for_load_state("domcontentloaded")
    # ⚠️ Подставьте селекторы полей/кнопки после первого запуска, если сайт поменяет разметку
    page.fill("input[name='login'], #login, input[name='username']", LOGIN)
    page.fill("input[type='password'], #password", PASSWORD)
    page.click("button:has-text('Войти'), input[type='submit']")
    page.wait_for_load_state("networkidle")

    # рассчитываем недели: от ближайшего понедельника (сегодня) на WEEKS_AHEAD вперёд
    today = datetime.now()
    start = monday_of(today)
    weeks = [start + timedelta(days=7*i) for i in range(WEEKS_AHEAD)]

    all_items = []
    for monday in weeks:
        week_from = fmt(monday)
        week_to   = fmt(monday + timedelta(days=6))
        url = f"{BASE_URL}?from={week_from}&to={week_to}"
        page.goto(url)
        page.wait_for_load_state("networkidle")
        all_items.extend(parse_week(page))

    # формируем .ics
    cal = Calendar()
    # простая дедупликация по ключу: дата+время+заголовок
    seen = set()
    for it in all_items:
        key = (it["date"].date(), it["start"], it["end"], it["title"])
        if key in seen: 
            continue
        seen.add(key)
        ev = Event()
        ev.name = it["title"]
        ev.begin = dt_local(it["date"], it["start"], TZ_NAME)
        ev.end   = dt_local(it["date"], it["end"], TZ_NAME)
        if it["desc"]:
            ev.description = it["desc"]
        cal.events.add(ev)

    with open("schedule.ics", "w", encoding="utf-8") as f:
        f.writelines(cal.serialize_iter())
