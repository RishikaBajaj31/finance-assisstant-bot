# Submission Checklist

## Done

- [x] `/health` endpoint returns `200 OK`
- [x] Telegram webhook route exists at `POST /webhook`
- [x] Docker build and compose startup work
- [x] PostgreSQL startup and schema bootstrapping are wired
- [x] Scheduler startup and shutdown are guarded
- [x] `.env` is ignored by git
- [x] `.env.example` lists required variables
- [x] Telegram webhook secret verification is optional and off by default
- [x] Deployment and run instructions are documented

## Before submitting

- [ ] Set `GEMINI_API_KEY` in `.env`
- [ ] Set `TELEGRAM_BOT_TOKEN` in `.env`
- [ ] Set `TELEGRAM_WEBHOOK_URL` to the public webhook URL
- [ ] Set `NEWS_API_KEY` if you want live news enrichment
- [ ] Set `TELEGRAM_WEBHOOK_SECRET_TOKEN` if you want header verification
- [ ] Confirm Docker is running
- [ ] Run the app with `docker compose up --build`
- [ ] Verify `GET /health`
- [ ] Verify `POST /webhook`
- [ ] Run tests before final submission
