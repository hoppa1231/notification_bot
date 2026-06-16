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
TELEGRAM_API_BASE_URL=https://api.telegram.org
ENABLE_DEBUG_NOTIFICATIONS=true
```

If the server cannot reach `api.telegram.org` directly, either add proxy environment variables to `.env`:

```env
HTTPS_PROXY=http://user:password@proxy-host:proxy-port
HTTP_PROXY=http://user:password@proxy-host:proxy-port
```

or point `TELEGRAM_API_BASE_URL` to a reachable compatible Telegram Bot API endpoint.

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

By default `docker-compose.yml` exposes the API on host port `2005`.

## CI/CD

GitHub Actions workflow: `.github/workflows/ci-cd.yml`.

It runs tests on every push and pull request. On push to `main`, or manual `workflow_dispatch`, it deploys to the server over SSH and restarts Docker Compose in `/opt/notification_bot`.

Required GitHub repository secrets:

- `SSH_HOST`: server hostname or IP, for example `moscow.example.com`.
- `SSH_USER`: SSH user, for example `root`.
- `SSH_PRIVATE_KEY`: private key with access to the server.
- `PROD_ENV_FILE`: full production `.env` content.

Required GitHub repository variable:

- `DEPLOY_ENABLED`: set to `true` after all deploy secrets are configured.

`PROD_ENV_FILE` example:

```env
TELEGRAM_BOT_TOKEN=123456789:replace_me
TELEGRAM_CHAT_ID=123456789
NOTIFY_API_TOKEN=replace_with_long_random_token
TELEGRAM_API_BASE_URL=https://api.telegram.org
ENABLE_DEBUG_NOTIFICATIONS=true
REQUEST_TIMEOUT_SECONDS=10
```

## Send Notification

```bash
curl -X POST "http://localhost:2005/notify" \
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
