"""System wide constants for AI Financial Assistant."""

DEFAULT_BRIEFING_TIME = "08:00"
DEFAULT_TIMEZONE = "UTC"
DEFAULT_EMBEDDING_DIM = 768

# Intent Categories
INTENT_ONBOARDING = "onboarding"
INTENT_RESEARCH = "research"
INTENT_NEWS = "news"
INTENT_DOCUMENT = "document"
INTENT_GENERAL = "general"

# Memory Types
MEMORY_TYPE_USER_FACT = "user_fact"
MEMORY_TYPE_PREFERENCE = "preference"
MEMORY_TYPE_WATCHLIST = "watchlist"

# Document Status
DOC_STATUS_UPLOADED = "uploaded"
DOC_STATUS_PROCESSING = "processing"
DOC_STATUS_READY = "ready"
DOC_STATUS_FAILED = "failed"

# Backwards-compatible alias
DOC_STATUS_PROCESSED = DOC_STATUS_READY

# Alert Types / Scopes / Actions
ALERT_TYPE_PRICE = "price_threshold"
ALERT_TYPE_PERCENT = "percent_move"
ALERT_TYPE_EARNINGS = "earnings"
ALERT_TYPE_NEWS = "major_news"

ALERT_SCOPE_TICKER = "ticker"
ALERT_SCOPE_WATCHLIST = "watchlist"

ALERT_ACTION_CREATE = "create"
ALERT_ACTION_LIST = "list"
ALERT_ACTION_CANCEL = "cancel"
ALERT_ACTION_UPDATE = "update"
