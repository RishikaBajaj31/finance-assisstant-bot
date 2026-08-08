# AI Financial Assistant

Production-oriented Telegram financial assistant scaffold built with FastAPI, LangGraph, SQLAlchemy async, PostgreSQL, Gemini, and yfinance.

## Run

```bash
docker compose up --build
```

## Main endpoints

- `GET /health`
- `POST /webhook`
- `GET /api/v1/users/{telegram_id}`
- `POST /api/v1/users/{telegram_id}/onboarding`
- `POST /api/v1/alerts/{user_id}`
- `GET /api/v1/alerts/{user_id}`

## Notes

- The app runs in offline fallback mode when Gemini or Telegram keys are not configured.
- PostgreSQL should have the `vector` extension available.
