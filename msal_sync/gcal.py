 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/msal_sync/gcal.py b/msal_sync/gcal.py
new file mode 100644
index 0000000000000000000000000000000000000000..39bcda51989664f1eb54c7202445fd3af7da9717
--- /dev/null
+++ b/msal_sync/gcal.py
@@ -0,0 +1,121 @@
+from __future__ import annotations
+
+import datetime as dt
+import logging
+from typing import List
+
+from google.auth.transport.requests import Request
+from google.oauth2.credentials import Credentials
+from google_auth_oauthlib.flow import InstalledAppFlow
+from googleapiclient.discovery import build
+
+from .models import Event
+from .utils import events_equal
+
+SCOPES = ["https://www.googleapis.com/auth/calendar"]
+
+
+def _load_credentials(client_secrets_file: str, token_file: str) -> Credentials:
+    creds = None
+    if token_file:
+        try:
+            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
+        except Exception:
+            creds = None
+    if not creds or not creds.valid:
+        if creds and creds.expired and creds.refresh_token:
+            creds.refresh(Request())
+        else:
+            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
+            creds = flow.run_local_server(port=0)
+        with open(token_file, "w") as token:
+            token.write(creds.to_json())
+    return creds
+
+
+def build_service(client_secrets_file: str, token_file: str):
+    creds = _load_credentials(client_secrets_file, token_file)
+    return build("calendar", "v3", credentials=creds)
+
+
+def fetch_existing_events(service, calendar_id: str, time_min: dt.datetime, time_max: dt.datetime) -> dict[str, dict]:
+    logging.info("Fetching existing events from %s to %s", time_min, time_max)
+    events: dict[str, dict] = {}
+    page_token = None
+    while True:
+        events_result = (
+            service.events()
+            .list(
+                calendarId=calendar_id,
+                timeMin=time_min.isoformat(),
+                timeMax=time_max.isoformat(),
+                singleEvents=True,
+                showDeleted=False,
+                maxResults=2500,
+                pageToken=page_token,
+            )
+            .execute()
+        )
+        for event in events_result.get("items", []):
+            props = event.get("extendedProperties", {}).get("private", {})
+            if props.get("managed_by") == "msal_schedule_sync" and "source_id" in props:
+                events[props["source_id"]] = event
+        page_token = events_result.get("nextPageToken")
+        if not page_token:
+            break
+    logging.info("Found %d existing managed events", len(events))
+    return events
+
+
+def sync_events(
+    service,
+    calendar_id: str,
+    parsed_events: List[Event],
+    time_min: dt.datetime,
+    time_max: dt.datetime,
+    dry_run: bool = False,
+    delete_missing: bool = False,
+):
+    existing = fetch_existing_events(service, calendar_id, time_min, time_max)
+    actions = []
+
+    for event in parsed_events:
+        body = event.to_gcal_body()
+        existing_event = existing.get(event.source_id)
+        if not existing_event:
+            actions.append(("CREATE", event, body, None))
+        else:
+            current = Event(
+                title=existing_event.get("summary", ""),
+                start=dt.datetime.fromisoformat(existing_event["start"]["dateTime"]),
+                end=dt.datetime.fromisoformat(existing_event["end"]["dateTime"]),
+                location=existing_event.get("location"),
+                description=existing_event.get("description"),
+                source_id=event.source_id,
+            )
+            if not events_equal(event, current):
+                actions.append(("UPDATE", event, body, existing_event))
+
+    if delete_missing:
+        managed_ids = {e.source_id for e in parsed_events}
+        for src_id, existing_event in existing.items():
+            if src_id not in managed_ids:
+                actions.append(("DELETE", None, None, existing_event))
+
+    for action, event, body, existing_event in actions:
+        if action == "CREATE":
+            logging.info("CREATE %s %s-%s", event.title, event.start, event.end)
+            if not dry_run:
+                service.events().insert(calendarId=calendar_id, body=body).execute()
+        elif action == "UPDATE":
+            logging.info("UPDATE %s %s-%s", event.title, event.start, event.end)
+            if not dry_run:
+                service.events().update(calendarId=calendar_id, eventId=existing_event["id"], body=body).execute()
+        elif action == "DELETE":
+            summary = existing_event.get("summary", "")
+            start = existing_event.get("start", {}).get("dateTime")
+            end = existing_event.get("end", {}).get("dateTime")
+            logging.info("DELETE %s %s-%s", summary, start, end)
+            if not dry_run:
+                service.events().delete(calendarId=calendar_id, eventId=existing_event["id"]).execute()
+    logging.info("Sync complete. %d actions", len(actions))
 
EOF
)
