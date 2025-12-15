from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    title: str
    start: datetime
    end: datetime
    location: Optional[str]
    description: Optional[str]
    source_id: str
    raw: Optional[dict] = field(default=None)

    def to_gcal_body(self) -> dict:
        body = {
            "summary": self.title,
            "start": {"dateTime": self.start.isoformat()},
            "end": {"dateTime": self.end.isoformat()},
            "extendedProperties": {
                "private": {
                    "managed_by": "msal_schedule_sync",
                    "source_id": self.source_id,
                }
            },
        }
        if self.location:
            body["location"] = self.location
        if self.description:
            body["description"] = self.description
        return body
