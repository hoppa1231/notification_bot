# Telegram Notification Bot

HTTP API that receives notifications from external systems and forwards them to a Telegram chat.

## Features

- `POST /notify` with Bearer token authorization.
- Notification types: `critical`, `info`, `debug`.
- `debug` notifications can be disabled through config.
- `GET /health` for uptime checks.
- Docker and docker-compose support.

## Setup

1. Create a bot with `@BotFather` and copy the bot token.
2. Send any message to the bot from your Telegram account.
3. Get your chat id:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates"
```

4. Create `.env`:

```bash
cp .env.example .env
```

5. Fill in:

```env
TELEGRAM_BOT_TOKEN=123456789:replace_me
TELEGRAM_CHAT_ID=123456789
NOTIFY_API_TOKEN=replace_with_long_random_token
ENABLE_DEBUG_NOTIFICATIONS=true
```

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Run With Docker

```bash
docker compose up --build
```

## Send Notification

```bash
curl -X POST "http://localhost:8000/notify" \
  -H "Authorization: Bearer replace_with_long_random_token" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "critical",
    "title": "Payment error",
    "message": "Payment #123 failed",
    "source": "billing-api"
  }'
```

Response:

```json
{
  "ok": true,
  "skipped": false,
  "reason": null
}
```

## API

### `GET /health`

Returns:

```json
{"status": "ok"}
```

### `POST /notify`

Body:

```json
{
  "type": "info",
  "title": "Build finished",
  "message": "Deployment completed successfully",
  "source": "ci"
}
```

Fields:

- `type`: one of `critical`, `info`, `debug`; defaults to `info`.
- `title`: required, 1-120 characters.
- `message`: required, 1-3500 characters.
- `source`: optional, up to 120 characters.
