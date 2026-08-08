# Deployment

## What runs

- FastAPI app on port `8000`
- PostgreSQL with `pgvector`
- Optional APScheduler jobs for daily briefings and alert checks

## Required environment variables

Set these in `.env` before running in Docker or locally:

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_URL`
- `NEWS_API_KEY` if you want live news lookups
- `DATABASE_URL` if you are not using the bundled Docker database

Optional values:

- `TELEGRAM_WEBHOOK_SECRET_TOKEN`
- `ENABLE_SCHEDULER`
- `DEFAULT_BRIEFING_TIME`
- `ENV`
- `LOG_LEVEL`

## Run locally

```powershell
docker compose up --build
```

The app listens on:

- `http://127.0.0.1:8000`

Health check:

- `GET /health`

Telegram webhook:

- `POST /webhook`

## Telegram webhook setup

If you set `TELEGRAM_WEBHOOK_SECRET_TOKEN`, configure Telegram to send the same value in the `X-Telegram-Bot-Api-Secret-Token` header.

If you do not set a secret token, the webhook still works without header verification.

## Database

Docker Compose starts PostgreSQL automatically.

If you run outside Docker, make sure `DATABASE_URL` points to a live PostgreSQL instance with `pgvector` available.

## Notes

- `.env` is ignored by git.
- `.env.example` contains variable names only.
- The app is safe to start without live Gemini or Telegram credentials, but real bot messaging requires valid keys.
