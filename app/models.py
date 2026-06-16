from enum import StrEnum

from pydantic import BaseModel, Field


class NotificationKind(StrEnum):
    critical = "critical"
    info = "info"
    debug = "debug"


class NotificationRequest(BaseModel):
    type: NotificationKind = Field(default=NotificationKind.info)
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=3500)
    source: str | None = Field(default=None, max_length=120)


class NotificationResponse(BaseModel):
    ok: bool
    skipped: bool = False
    reason: str | None = None
