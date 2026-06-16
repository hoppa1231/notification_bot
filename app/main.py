import logging
import secrets
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, status

from app.config import Settings
from app.models import NotificationKind, NotificationRequest, NotificationResponse
from app.telegram import TelegramClient

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Telegram Notification Bot",
    version="0.1.0",
    description="Small HTTP API for forwarding external notifications to Telegram.",
)


@lru_cache
def load_settings() -> Settings:
    return Settings.from_env()


async def get_settings() -> Settings:
    return load_settings()


async def authorize(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.notify_api_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="NOTIFY_API_TOKEN is not configured",
        )

    scheme, _, token = (authorization or "").partition(" ")
    is_valid = scheme.lower() == "bearer" and secrets.compare_digest(token, expected)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_telegram_client(settings: Settings = Depends(get_settings)) -> TelegramClient:
    return TelegramClient(settings)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/notify",
    response_model=NotificationResponse,
    dependencies=[Depends(authorize)],
)
async def notify(
    notification: NotificationRequest,
    settings: Settings = Depends(get_settings),
    telegram: TelegramClient = Depends(get_telegram_client),
) -> NotificationResponse:
    if notification.type == NotificationKind.debug and not settings.enable_debug_notifications:
        logger.info("Skipped debug notification from source=%s", notification.source)
        return NotificationResponse(ok=True, skipped=True, reason="debug notifications disabled")

    try:
        await telegram.send_message(notification)
    except Exception as exc:
        logger.exception("Failed to send Telegram notification")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send Telegram notification",
        ) from exc

    logger.info("Sent %s notification from source=%s", notification.type, notification.source)
    return NotificationResponse(ok=True)
