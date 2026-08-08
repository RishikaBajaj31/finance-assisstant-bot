"""Prompts for long-term memory extraction."""

MEMORY_EXTRACTION_SYSTEM_PROMPT = (
    "Determine whether the user's latest message contains a durable financial preference or profile fact.\n"
    "Return valid JSON only with these keys:\n"
    "{"
    '"should_remember": boolean, '
    '"memory_type": string, '
    '"content": string|null, '
    '"importance": number, '
    '"memory_key": string|null'
    "}.\n"
    "Only store durable facts such as role, industries, recurring preferences, follow lists, or briefing preferences.\n"
    "Do not store transient chatter."
)

MEMORY_CONTEXT_SYSTEM_PROMPT = (
    "Use the supplied relevant memories as context, but only if they help answer the user's question.\n"
    "Keep the reply concise and conversational."
)
