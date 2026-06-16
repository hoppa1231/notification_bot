import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    notify_api_token: str
    telegram_api_base_url: str = "https://api.telegram.org"
    enable_debug_notifications: bool = True
    request_timeout_seconds: int = 10

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            notify_api_token=os.getenv("NOTIFY_API_TOKEN", ""),
            telegram_api_base_url=os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org").rstrip("/"),
            enable_debug_notifications=_env_bool("ENABLE_DEBUG_NOTIFICATIONS", True),
            request_timeout_seconds=_env_int("REQUEST_TIMEOUT_SECONDS", 10),
        )

    def validate_runtime(self) -> None:
        missing = [
            name
            for name, value in {
                "TELEGRAM_BOT_TOKEN": self.telegram_bot_token,
                "TELEGRAM_CHAT_ID": self.telegram_chat_id,
                "NOTIFY_API_TOKEN": self.notify_api_token,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
