import asyncio

import httpx

from app.config import Settings
from app.main import app, get_settings, get_telegram_client


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent = []

    async def send_message(self, notification):
        self.sent.append(notification)


def make_transport(settings: Settings, telegram: FakeTelegramClient | None = None):
    async def override_settings() -> Settings:
        return settings

    app.dependency_overrides[get_settings] = override_settings
    if telegram is not None:
        async def override_telegram() -> FakeTelegramClient:
            return telegram

        app.dependency_overrides[get_telegram_client] = override_telegram
    else:
        app.dependency_overrides.pop(get_telegram_client, None)
    return httpx.ASGITransport(app=app)


async def request(method: str, url: str, **kwargs) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.request(method, url, **kwargs)


async def request_with_settings(
    settings: Settings,
    method: str,
    url: str,
    telegram: FakeTelegramClient | None = None,
    **kwargs,
) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=make_transport(settings, telegram),
        base_url="http://testserver",
    ) as client:
        return await client.request(method, url, **kwargs)


def teardown_function():
    app.dependency_overrides.clear()


def test_health():
    response = asyncio.run(request("GET", "/health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_notify_requires_bearer_token():
    response = asyncio.run(
        request_with_settings(
            Settings(
                telegram_bot_token="bot",
                telegram_chat_id="chat",
                notify_api_token="secret",
            ),
            "POST",
            "/notify",
            json={"title": "Hi", "message": "Body"},
        )
    )

    assert response.status_code == 401


def test_notify_sends_message():
    telegram = FakeTelegramClient()
    response = asyncio.run(
        request_with_settings(
            Settings(
                telegram_bot_token="bot",
                telegram_chat_id="chat",
                notify_api_token="secret",
            ),
            "POST",
            "/notify",
            telegram,
            headers={"Authorization": "Bearer secret"},
            json={
                "type": "critical",
                "title": "Payment error",
                "message": "Payment #123 failed",
                "source": "billing-api",
            },
        )
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "skipped": False, "reason": None}
    assert len(telegram.sent) == 1
    assert telegram.sent[0].type == "critical"


def test_debug_notification_can_be_disabled():
    telegram = FakeTelegramClient()
    response = asyncio.run(
        request_with_settings(
            Settings(
                telegram_bot_token="bot",
                telegram_chat_id="chat",
                notify_api_token="secret",
                enable_debug_notifications=False,
            ),
            "POST",
            "/notify",
            telegram,
            headers={"Authorization": "Bearer secret"},
            json={"type": "debug", "title": "Trace", "message": "Something happened"},
        )
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "skipped": True,
        "reason": "debug notifications disabled",
    }
    assert telegram.sent == []
