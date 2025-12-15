 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/msal_sync/parser.py b/msal_sync/parser.py
new file mode 100644
index 0000000000000000000000000000000000000000..a18a6c09325df8e162936594610f17cb1b13ffdd
--- /dev/null
+++ b/msal_sync/parser.py
@@ -0,0 +1,195 @@
+from __future__ import annotations
+
+import logging
+import re
+from collections import defaultdict
+from datetime import date
+from typing import List, Optional
+from zoneinfo import ZoneInfo
+
+from bs4 import BeautifulSoup
+
+from .config import MONTHS_RU
+from .models import Event
+from .utils import build_datetime, hash_source
+
+DATE_REGEX = re.compile(r"\b\d{1,2}\s+[А-Яа-я]+\s+\d{4}\b")
+TIME_REGEX = re.compile(r"\b\d{2}:\d{2}\b")
+
+
+class ParseError(Exception):
+    pass
+
+
+def parse_ru_date(s: str) -> date:
+    parts = s.strip().split()
+    if len(parts) != 3:
+        raise ValueError(f"Cannot parse date from '{s}'")
+    day_str, month_ru, year_str = parts
+    day = int(day_str)
+    year = int(year_str)
+    month = MONTHS_RU.get(month_ru.lower())
+    if not month:
+        raise ValueError(f"Unknown month '{month_ru}' in '{s}'")
+    return date(year, month, day)
+
+
+def _extract_dates(schedule_root: BeautifulSoup) -> List[date]:
+    headers = schedule_root.select("div.table-header div.table-header-columns")
+    dates: List[date] = []
+    for header in headers:
+        match = DATE_REGEX.search(header.get_text(" ", strip=True))
+        if match:
+            try:
+                dates.append(parse_ru_date(match.group(0)))
+            except Exception as exc:
+                logging.warning("Failed to parse date '%s': %s", match.group(0), exc)
+    if len(dates) != 7:
+        logging.warning("Expected 7 dates in header, got %d", len(dates))
+    return dates
+
+
+def _extract_text(node) -> str:
+    return node.get_text(" ", strip=True) if node else ""
+
+
+def _extract_times(card) -> Optional[tuple[str, str]]:
+    times = TIME_REGEX.findall(card.get_text(" ", strip=True))
+    if len(times) >= 2:
+        return times[0], times[1]
+    return None
+
+
+def _extract_lesson_type(card) -> Optional[str]:
+    span = card.find("span", attrs={"title": True})
+    if span:
+        return _extract_text(span)
+    return None
+
+
+def _extract_subject(card) -> str:
+    subject_block = card.find(attrs={"class": re.compile(r"mb-1")})
+    if not subject_block:
+        return ""
+    direct = subject_block.find("div", class_=re.compile(r"text-left"))
+    if direct:
+        text = _extract_text(direct)
+        if text:
+            return text
+    btn = subject_block.find("button")
+    if btn:
+        text = _extract_text(btn)
+        if text:
+            return text
+    return _extract_text(subject_block)
+
+
+def _extract_location_and_lines(card) -> tuple[Optional[str], list[str], list[str]]:
+    ten_px_lines = [
+        _extract_text(p)
+        for p in card.find_all("p", class_=re.compile(r"text-\[10px\]"))
+    ]
+    location: Optional[str] = None
+    extras: list[str] = []
+    subgroups: list[str] = []
+    for line in ten_px_lines:
+        if not line:
+            continue
+        if line.startswith("Подгруппы"):
+            subgroups.append(line)
+            continue
+        if location is None:
+            location = line
+        else:
+            extras.append(line)
+    return location, extras, subgroups
+
+
+def _extract_teacher(card) -> Optional[str]:
+    teacher_line = card.find("p", class_=re.compile(r"text-\[12px\]"))
+    if teacher_line:
+        text = _extract_text(teacher_line)
+        if text:
+            return text
+    return None
+
+
+def _is_remote(card) -> bool:
+    return bool(card.find("button", attrs={"title": "Удаленное занятие"}))
+
+
+def parse_events_from_html(html: str, tz: ZoneInfo) -> List[Event]:
+    soup = BeautifulSoup(html, "lxml")
+    schedule_root = soup.select_one("div.days-schedule")
+    if not schedule_root:
+        raise ParseError("Schedule root not found")
+
+    dates = _extract_dates(schedule_root)
+    if not dates:
+        raise ParseError("No dates found in header")
+
+    events: List[Event] = []
+    source_counts: dict[str, int] = defaultdict(int)
+
+    data_rows = schedule_root.select("div.table-data")
+    for row in data_rows:
+        day_cells = [child for child in row.find_all("div", recursive=False) if "border" in child.get("class", [])]
+        if len(day_cells) != len(dates):
+            logging.warning("Day cells count %d does not match dates %d", len(day_cells), len(dates))
+        for idx, cell in enumerate(day_cells[: len(dates)]):
+            cards = cell.find_all("div", class_=re.compile(r"shadow-md"))
+            for card in cards:
+                times = _extract_times(card)
+                if not times:
+                    logging.debug("Skipping card without times")
+                    continue
+                start_str, end_str = times
+                lesson_type = _extract_lesson_type(card)
+                subject = _extract_subject(card) or "Без названия"
+                location, extra_lines, subgroups = _extract_location_and_lines(card)
+                teacher = _extract_teacher(card)
+                is_remote = _is_remote(card)
+
+                lesson_date = dates[idx]
+                start_dt = build_datetime(lesson_date, start_str, tz)
+                end_dt = build_datetime(lesson_date, end_str, tz)
+
+                description_lines: list[str] = []
+                if lesson_type:
+                    description_lines.append(f"Тип: {lesson_type}")
+                if teacher:
+                    description_lines.append(f"Преподаватель: {teacher}")
+                for sg in subgroups:
+                    description_lines.append(sg.replace("Подгруппы:", "Подгруппа:").strip())
+                if is_remote:
+                    description_lines.append("Формат: дистанционно")
+                for line in extra_lines:
+                    description_lines.append(line)
+
+                description = "\n".join(description_lines) if description_lines else None
+
+                location_for_id = location or ""
+                base_key = "|".join(
+                    [
+                        lesson_date.isoformat(),
+                        start_str,
+                        end_str,
+                        subject.strip(),
+                        location_for_id.strip(),
+                    ]
+                )
+                source_counts[base_key] += 1
+                suffix = "" if source_counts[base_key] == 1 else f"|#{source_counts[base_key]-1}"
+                source_id = hash_source([base_key + suffix])
+
+                event = Event(
+                    title=subject.strip(),
+                    start=start_dt,
+                    end=end_dt,
+                    location=location.strip() if location else None,
+                    description=description,
+                    source_id=source_id,
+                    raw=None,
+                )
+                events.append(event)
+    return events
 
EOF
)
