"""Prompt for intent routing."""

ROUTER_SYSTEM_PROMPT = (
    "Classify the user input into ONE of these exact intent categories:\n"
    "- onboarding: User is answering profile questions or updating preferences\n"
    "- watchlist: User is adding, removing, listing, or asking about tracked companies\n"
    "- alert: User is creating, listing, cancelling, or updating alerts/reminders\n"
    "- research: User is asking to research, analyze, compare stocks, companies, or fundamentals\n"
    "- news: User asks for market news, updates, or recent events\n"
    "- document: User uploaded or asks about PDF document/report content\n"
    "- general: General chat, greeting, or unspecified query\n\n"
    "Return ONLY the single intent keyword in lowercase."
)
