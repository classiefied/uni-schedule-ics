 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/msal_sync/utils.py b/msal_sync/utils.py
new file mode 100644
index 0000000000000000000000000000000000000000..60fb280d99cdf884264a182c165863d86de67a22
--- /dev/null
+++ b/msal_sync/utils.py
@@ -0,0 +1,41 @@
+from __future__ import annotations
+
+import hashlib
+from datetime import date, datetime
+from typing import Iterable, List, Tuple
+from zoneinfo import ZoneInfo
+
+from .models import Event
+
+
+def build_datetime(day: date, time_str: str, tz: ZoneInfo) -> datetime:
+    hour, minute = [int(x) for x in time_str.split(":", 1)]
+    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
+
+
+def hash_source(parts: Iterable[str]) -> str:
+    hasher = hashlib.sha1()
+    joined = "|".join(parts)
+    hasher.update(joined.encode("utf-8"))
+    return hasher.hexdigest()
+
+
+def events_equal(a: Event, b: Event) -> bool:
+    return (
+        a.title == b.title
+        and a.start == b.start
+        and a.end == b.end
+        and (a.location or "") == (b.location or "")
+        and (a.description or "") == (b.description or "")
+    )
+
+
+def partition_events_by_source(events: List[Event]) -> Tuple[dict[str, Event], dict[str, list[Event]]]:
+    unique: dict[str, Event] = {}
+    duplicates: dict[str, list[Event]] = {}
+    for event in events:
+        if event.source_id in unique:
+            duplicates.setdefault(event.source_id, [unique[event.source_id]]).append(event)
+        else:
+            unique[event.source_id] = event
+    return unique, duplicates
 
EOF
)
