# Phase 1-3 Status

## Implemented

- Conversational onboarding
  - The assistant now extracts onboarding details from natural language.
  - It saves role, briefing time, timezone, sectors, interests, and watchlist companies.
  - It can skip onboarding when the user explicitly wants to start immediately.

- Long-term memory
  - The assistant now stores durable user memories from conversation context.
  - Duplicate memories are merged by memory key instead of creating repeats.
  - Relevant memories are included in the response prompt.

- Conversational watchlist management
  - Users can add, remove, list, and update tracked companies in plain language.
  - Company names are resolved to tickers through aliases and market lookup.
  - Watchlist actions are routed through the agent graph and Telegram webhook.

- Database and startup support
  - Schema migration support now adds the `memory_key` column when missing.
  - Application startup ensures schema compatibility before serving traffic.
  - Shutdown now disposes the async engine cleanly.

- Tests
  - Added integration coverage for onboarding, memory, ticker resolution, and watchlist flows.
  - Added database reset helpers for repeatable test execution.

## Left

- Optional production hardening:
  - Replace legacy FastAPI `on_event` handlers with lifespan handlers.
  - Add more precise semantic recall instead of falling back to broad memory retrieval.
  - Expand company alias coverage over time.

- Environment setup still required for real usage:
  - `GEMINI_API_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_WEBHOOK_URL`
  - `NEWS_API_KEY`
  - `DATABASE_URL` if you are not using the default local Postgres setup

## Verification

- `python -m compileall app tests`
- `python -m pytest -q`

Result: `16 passed`

