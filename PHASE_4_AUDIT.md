# Phase 4 Audit

## Already Working

- Existing document ORM models and pgvector-backed chunk storage exist in [`app/models/document.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/models/document.py).
- A document repository abstraction already exists through [`app/database/repositories/document_repo.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/repositories/document_repo.py) and the shared repository module.
- The LangGraph already has a document branch in [`app/agents/graph.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/graph.py).
- A document node already exists in [`app/agents/nodes/document_node.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/nodes/document_node.py).
- Gemini embedding and response helpers already exist in [`app/integrations/gemini.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/integrations/gemini.py).
- PDF extraction support already existed through `pdfplumber` in the document service.

## Missing / Incomplete

- Telegram webhook handling did not accept file uploads.
- Document records did not store enough upload metadata:
  - telegram file id
  - content type
  - size
  - page count
  - processing timestamps
  - extraction error details
- Document chunks did not retain page number metadata.
- Document ingestion did not validate file type or size.
- The document service used placeholder fallback text for extraction failure.
- Document retrieval did not enforce strict document-grounded answers with source citations.
- Router logic did not reliably treat follow-up questions as document questions after an upload.

## Files To Change

- [`app/models/document.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/models/document.py)
- [`app/database/migrations/init.sql`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/migrations/init.sql)
- [`app/database/migrations/ensure_schema.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/migrations/ensure_schema.py)
- [`app/database/repositories/watchlist_repo.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/database/repositories/watchlist_repo.py)
- [`app/services/document_service.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/services/document_service.py)
- [`app/agents/nodes/router_node.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/agents/nodes/router_node.py)
- [`app/telegram/bot.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/telegram/bot.py)
- [`app/telegram/handlers.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/telegram/handlers.py)
- [`app/prompts/document.py`](C:/Users/rishi/OneDrive/Desktop/financial-assisstant/app/prompts/document.py)
- Tests under `tests/` for upload handling, extraction, chunking, retrieval, comparison, and user isolation

