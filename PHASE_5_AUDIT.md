# Phase 5 Audit

## Already Working

- There is already an `alerts` table and ORM model in [`app/models/watchlist.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/models/watchlist.py).
- There is already an alert repository path in [`app/database/repositories/watchlist_repo.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/repositories/watchlist_repo.py).
- There is already a basic alert evaluation service in [`app/services/alert_service.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/services/alert_service.py).
- The scheduler already runs an alert polling job in [`app/scheduler/alert_job.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/scheduler/alert_job.py).
- The Telegram bot wrapper already sends messages in [`app/telegram/bot.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/telegram/bot.py).
- The LangGraph router already supports intent-based branching in [`app/agents/graph.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/graph.py) and [`app/agents/nodes/router_node.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/nodes/router_node.py).
- The finance stack already has yfinance and news integrations in [`app/integrations/yfinance_client.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/integrations/yfinance_client.py) and [`app/services/news_service.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/services/news_service.py).

## Incomplete

- Alerts only support basic price-above / price-below polling.
- There is no natural-language alert creation or cancellation path in the agent graph.
- The alert model is missing fields for alert type, reminder timing, news/watchlist scope, and notification timestamps.
- Scheduler evaluation does not handle:
  - percent-move alerts
  - earnings reminders
  - major news alerts
  - duplicate notification prevention
- Telegram notifications are not yet generated from triggered alerts.
- User timezone is not yet used for reminder calculation.
- Alert list/cancel flows are only available through the thin API and not conversationally.

## Reusable

- The current alert table, repository, and scheduler job structure.
- Existing company resolution, watchlist data, yfinance, and Telegram delivery.
- Existing LangGraph routing architecture.

## Files Requiring Changes

- [`app/models/watchlist.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/models/watchlist.py)
- [`app/database/migrations/init.sql`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/migrations/init.sql)
- [`app/database/migrations/ensure_schema.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/migrations/ensure_schema.py)
- [`app/database/repositories/watchlist_repo.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/repositories/watchlist_repo.py)
- [`app/services/alert_service.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/services/alert_service.py)
- [`app/integrations/yfinance_client.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/integrations/yfinance_client.py)
- [`app/prompts/router.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/prompts/router.py)
- [`app/agents/graph.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/graph.py)
- [`app/agents/nodes/router_node.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/nodes/router_node.py)
- [`app/api/alerts.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/api/alerts.py)
- [`app/scheduler/alert_job.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/scheduler/alert_job.py)
- [`app/telegram/bot.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/telegram/bot.py)
- New alert prompt and alert node files
- New tests for alert creation, cancellation, evaluation, duplicate prevention, and Telegram delivery

