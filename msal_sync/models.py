 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/msal_sync/models.py b/msal_sync/models.py
new file mode 100644
index 0000000000000000000000000000000000000000..56ddaf496508403383a071f7e25f57b74376fad4
--- /dev/null
+++ b/msal_sync/models.py
@@ -0,0 +1,34 @@
+from __future__ import annotations
+
+from dataclasses import dataclass, field
+from datetime import datetime
+from typing import Optional
+
+
+@dataclass
+class Event:
+    title: str
+    start: datetime
+    end: datetime
+    location: Optional[str]
+    description: Optional[str]
+    source_id: str
+    raw: Optional[dict] = field(default=None)
+
+    def to_gcal_body(self) -> dict:
+        body = {
+            "summary": self.title,
+            "start": {"dateTime": self.start.isoformat()},
+            "end": {"dateTime": self.end.isoformat()},
+            "extendedProperties": {
+                "private": {
+                    "managed_by": "msal_schedule_sync",
+                    "source_id": self.source_id,
+                }
+            },
+        }
+        if self.location:
+            body["location"] = self.location
+        if self.description:
+            body["description"] = self.description
+        return body
 
EOF
)
