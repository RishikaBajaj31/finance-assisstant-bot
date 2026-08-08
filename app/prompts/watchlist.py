"""Prompts for watchlist management."""

WATCHLIST_EXTRACTION_SYSTEM_PROMPT = (
    "Extract a conversational watchlist request from the user's message.\n"
    "Return valid JSON only with these keys:\n"
    "{"
    '"action": "add"|"remove"|"list"|"summary"|"unknown", '
    '"companies": string[], '
    '"tickers": string[], '
    '"skip": boolean'
    "}.\n"
    "If the user asks what they are watching or show their watchlist, action should be list.\n"
    "If they ask what is happening with their watchlist, action should be summary."
)
