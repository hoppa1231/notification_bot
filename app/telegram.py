import html

import httpx

from app.config import Settings
from app.models import NotificationKind, NotificationRequest


LABELS = {
    NotificationKind.critical: ("CRITICAL", "🚨"),
    NotificationKind.info: ("INFO", "ℹ️"),
    NotificationKind.debug: ("DEBUG", "🛠"),
}


def format_notification(notification: NotificationRequest) -> str:
    label, icon = LABELS[notification.type]
    parts = [
        f"{icon} <b>{label}</b>",
        "",
        f"<b>{html.escape(notification.title)}</b>",
        html.escape(notification.message),
    ]

    if notification.source:
        parts.extend(["", f"<i>Source:</i> {html.escape(notification.source)}"])

    return "\n".join(parts)


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def send_message(self, notification: NotificationRequest) -> None:
        self._settings.validate_runtime()
        url = f"https://api.telegram.org/bot{self._settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self._settings.telegram_chat_id,
            "text": format_notification(notification),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            response = await client.post(url, json=payload)

        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            description = result.get("description", "unknown Telegram API error")
            raise RuntimeError(description)
