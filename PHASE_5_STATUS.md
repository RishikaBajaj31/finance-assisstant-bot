# Phase 5 Status

| Feature | Status | Tests | Notes |
|---|---|---|---|
| Natural-language price alerts | Done | `tests/test_phase5_alerts.py::test_natural_language_price_alert_creation` | Creates `below` / `above` price alerts from conversational text. |
| Natural-language percentage alerts | Done | `tests/test_phase5_alerts.py::test_natural_language_percentage_alert_creation` | Creates daily move alerts from conversational text. |
| Earnings reminders | Done | `tests/test_phase5_alerts.py::test_earnings_alert_creation` | Uses verified earnings dates and reminder offsets. |
| Major news alerts | Done | `tests/test_phase5_alerts.py::test_news_alert_creation` | Supports watchlist-scoped monitoring for major company news. |
| Invalid / ambiguous company handling | Done | `tests/test_phase5_alerts.py::test_invalid_ticker_rejected`, `tests/test_phase5_alerts.py::test_ambiguous_company_rejected` | The assistant asks for clarification instead of creating unresolved alerts. |
| Alert listing / cancellation | Done | `tests/test_phase5_alerts.py::test_alert_persistence_and_listing`, `tests/test_phase5_alerts.py::test_alert_cancellation` | Conversational list and cancel flows work through LangGraph. |
| Alert triggering | Done | `tests/test_phase5_alerts.py::test_price_condition_triggering`, `tests/test_phase5_alerts.py::test_percentage_condition_triggering`, `tests/test_phase5_alerts.py::test_earnings_reminder_triggering` | Scheduler evaluation handles price, percent, and earnings conditions. |
| Duplicate trigger prevention | Done | `tests/test_phase5_alerts.py::test_duplicate_trigger_prevention` | One-time alerts deactivate after firing. |
| Telegram alert notifications | Done | `tests/test_phase5_alerts.py::test_telegram_notification` | Triggered alerts are delivered through Telegram. |
| User isolation | Done | `tests/test_phase5_alerts.py::test_user_isolation` | Alerts are scoped to the owning application user. |
| Timezone handling | Done | `tests/test_phase5_alerts.py::test_timezone_handling` | User timezone is passed into alert extraction / handling context. |
| Scheduler failure isolation | Done | `tests/test_phase5_alerts.py::test_scheduler_failure_isolation` | One bad alert does not stop the rest. |
| API failure handling | Done | `tests/test_phase5_alerts.py::test_api_failure_handling` | News / market failures fail safely without crashing the job. |

## Files Changed

- [`app/models/watchlist.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/models/watchlist.py)
- [`app/database/migrations/init.sql`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/migrations/init.sql)
- [`app/database/migrations/ensure_schema.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/migrations/ensure_schema.py)
- [`app/core/constants.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/core/constants.py)
- [`app/prompts/alerts.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/prompts/alerts.py)
- [`app/prompts/router.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/prompts/router.py)
- [`app/database/repositories/watchlist_repo.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/repositories/watchlist_repo.py)
- [`app/integrations/yfinance_client.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/integrations/yfinance_client.py)
- [`app/services/alert_service.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/services/alert_service.py)
- [`app/agents/nodes/alert_node.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/nodes/alert_node.py)
- [`app/agents/nodes/router_node.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/nodes/router_node.py)
- [`app/agents/graph.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/graph.py)
- [`app/api/alerts.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/api/alerts.py)
- [`app/scheduler/alert_job.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/scheduler/alert_job.py)
- [`PHASE_5_AUDIT.md`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/PHASE_5_AUDIT.md)
- [`tests/test_phase5_alerts.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/tests/test_phase5_alerts.py)

## Database Changes

- Expanded the `alerts` table to support:
  - `alert_type`
  - `operator`
  - `reminder_minutes`
  - `scope`
  - `title`
  - `details`
  - `is_active`
  - `last_notified_at`
  - `triggered_at`
  - `reminder_at_utc`
  - `event_at_utc`
- Relaxed old price-only constraints so non-price alerts can be stored.
- Kept the existing alert table and repository rather than introducing a second alert system.

## Scheduler Changes

- The scheduler now evaluates all active alerts, not just price thresholds.
- One bad alert is isolated so it cannot stop the rest of the batch.
- Triggered alerts are deactivated after firing to prevent duplicate notifications.
- Telegram delivery happens from the alert polling job after trigger detection.

## Telegram Notification Changes

- Triggered alerts now send a direct Telegram message.
- Messages are concise and alert-type specific.
- Delivery failures are logged safely and do not crash the job.

## Environment Variables

No new required environment variables were added for Phase 5.

Existing runtime variables still matter:

- `GEMINI_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_URL`
- `NEWS_API_KEY`
- `DATABASE_URL`

## Tests Added

- `tests/test_phase5_alerts.py`
- Coverage includes:
  - natural-language alert creation
  - listing
  - cancellation
  - price trigger evaluation
  - percentage trigger evaluation
  - earnings reminder evaluation
  - duplicate prevention
  - Telegram notification
  - user isolation
  - timezone handling
  - scheduler failure isolation
  - API failure handling

## Test Results

- `python -m compileall app tests`
- `python -m pytest -q`

Result: `46 passed`

## Manual Telegram Test Procedure

1. Start the bot and scheduler.
2. Send: `Add Nvidia to my watchlist.`
3. Send: `Alert me if Nvidia falls below $150.`
4. Send: `What alerts do I have?`
5. Simulate a test price below the threshold and verify the bot sends a Telegram notification.
6. Send: `Cancel my Nvidia alert.`
7. Send: `Notify me if Tesla moves more than 5% today.`
8. Send: `Remind me one hour before Apple's next earnings.`
9. Verify each alert is created, listed, triggered, and cancelled conversationally without commands.

## Known Limitations

- Major-news alerts are intentionally conservative and may stay silent if the signal is weak.
- Alerts are one-time by default to prevent spam; recurring alert modes are not expanded in this phase.
- The app still uses FastAPI `on_event` lifecycle hooks, which FastAPI now deprecates in favor of lifespan handlers.

