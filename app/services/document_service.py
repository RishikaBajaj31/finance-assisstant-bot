"""Document ingestion and retrieval service for financial PDFs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence
from uuid import UUID

import pdfplumber
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DOC_STATUS_FAILED, DOC_STATUS_PROCESSING, DOC_STATUS_READY, DOC_STATUS_UPLOADED
from app.core.exceptions import DocumentParseException
from app.core.logging import logger
from app.database.repositories.document_repo import DocumentRepository
from app.integrations.gemini import gemini_client
from app.prompts.document import DOCUMENT_SYSTEM_PROMPT


MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP = 120
MAX_QUERY_DOCUMENTS = 2


@dataclass
class DocumentSelection:
    documents: list
    comparison: bool = False


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _split_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> List[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    if len(cleaned) <= max_chars:
        return [cleaned]

    chunks: List[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def _page_tokens(filename: str) -> set[str]:
    stem = Path(filename).stem
    normalized = _normalize_text(stem)
    return {token for token in normalized.split() if len(token) > 2}


class DocumentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.doc_repo = DocumentRepository(session)

    async def _extract_pdf_pages(self, file_path: str) -> tuple[list[dict], int]:
        try:
            with pdfplumber.open(file_path) as pdf:
                pages = []
                for page_number, page in enumerate(pdf.pages, start=1):
                    text = (page.extract_text() or "").strip()
                    pages.append({"page_number": page_number, "text": text})
                return pages, len(pdf.pages)
        except DocumentParseException:
            raise
        except Exception as exc:
            logger.error("Failed to extract PDF text from %s: %s", file_path, exc)
            raise DocumentParseException("Could not parse the PDF.")

    def _build_chunks(self, page_texts: Sequence[dict]) -> list[dict]:
        chunks: list[dict] = []
        chunk_index = 0
        for page in page_texts:
            page_number = page["page_number"]
            page_chunks = _split_text(page["text"])
            for text in page_chunks:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "page_number": page_number,
                        "content": text,
                    }
                )
                chunk_index += 1
        return chunks

    async def process_uploaded_document(
        self,
        user_id: UUID,
        file_path: str,
        filename: str,
        telegram_file_id: Optional[str] = None,
        content_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ):
        """Extract, chunk, embed, and store a PDF document."""
        doc = await self.doc_repo.create_document(
            user_id=user_id,
            filename=filename,
            file_type="pdf",
            telegram_file_id=telegram_file_id,
            content_type=content_type,
            size_bytes=size_bytes,
            status=DOC_STATUS_UPLOADED,
        )
        await self.doc_repo.mark_processing(doc.id)

        try:
            page_texts, page_count = await self._extract_pdf_pages(file_path)
            if not page_texts or not any(page["text"] for page in page_texts):
                raise DocumentParseException(
                    "The uploaded PDF appears scanned or image-based and has no extractable text."
                )

            chunks = self._build_chunks(page_texts)
            if not chunks:
                raise DocumentParseException("The uploaded PDF did not contain usable text.")

            indexed_chunks = []
            for chunk in chunks:
                embedding = await gemini_client.generate_embedding(chunk["content"])
                indexed_chunks.append({**chunk, "embedding": embedding})

            await self.doc_repo.add_chunks(doc.id, indexed_chunks)
            await self.doc_repo.mark_ready(doc.id, page_count=page_count)
            refreshed = await self.doc_repo.get_by_id(doc.id)
            return refreshed or doc
        except DocumentParseException as exc:
            await self.doc_repo.mark_failed(doc.id, str(exc))
            raise
        except Exception as exc:
            logger.error("Failed to process uploaded document %s: %s", filename, exc)
            await self.doc_repo.mark_failed(doc.id, "Unexpected document processing failure.")
            raise DocumentParseException("Could not process the PDF.")

    async def process_pdf(
        self,
        user_id: UUID,
        file_path: str,
        filename: str,
        telegram_file_id: Optional[str] = None,
        content_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
    ):
        """Backward-compatible alias for PDF ingestion."""
        return await self.process_uploaded_document(
            user_id=user_id,
            file_path=file_path,
            filename=filename,
            telegram_file_id=telegram_file_id,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    async def has_document_context(self, user_id: UUID) -> bool:
        return bool(await self.doc_repo.get_latest_ready_document(user_id))

    async def _select_documents(self, user_id: UUID, query: str) -> DocumentSelection:
        docs = await self.doc_repo.get_latest_ready_documents(user_id, limit=5)
        if not docs:
            return DocumentSelection(documents=[], comparison=False)

        lowered = query.lower()
        comparison = any(keyword in lowered for keyword in ("compare", "comparison", "vs", "versus", "difference", "between"))
        explicit = [doc for doc in docs if self._matches_document_query(doc.filename, lowered)]

        if comparison:
            selected = docs[:MAX_QUERY_DOCUMENTS]
            return DocumentSelection(documents=selected, comparison=True)

        if explicit:
            return DocumentSelection(documents=explicit[:MAX_QUERY_DOCUMENTS], comparison=False)

        if any(keyword in lowered for keyword in ("latest report", "most recent", "this report", "that report", "the report", "this one", "that one", "summary", "summarize", "risk", "revenue", "guidance", "management")):
            return DocumentSelection(documents=docs[:1], comparison=False)

        return DocumentSelection(documents=docs[:1], comparison=False)

    def _matches_document_query(self, filename: str, lowered_query: str) -> bool:
        filename_tokens = _page_tokens(filename)
        if not filename_tokens:
            return False
        return any(token in lowered_query for token in filename_tokens)

    def _build_context(self, chunks, document_lookup: dict[UUID, object]) -> tuple[str, str]:
        if not chunks:
            return "", ""

        grouped: dict[UUID, list] = {}
        for chunk in chunks:
            grouped.setdefault(chunk.document_id, []).append(chunk)

        sections: list[str] = []
        citations: list[str] = []
        for document_id, doc_chunks in grouped.items():
            document = document_lookup.get(document_id)
            filename = getattr(document, "filename", "Uploaded report")
            pages = sorted({chunk.page_number for chunk in doc_chunks if chunk.page_number is not None})
            page_label = ", ".join(str(page) for page in pages) if pages else "unknown pages"
            citations.append(f"{filename}: pages {page_label}")
            sections.append(f"[Document: {filename} | Pages: {page_label}]")
            for chunk in doc_chunks:
                sections.append(
                    f"- Page {chunk.page_number or 'unknown'} | Chunk {chunk.chunk_index}: {chunk.content}"
                )

        return "\n".join(sections), "; ".join(citations)

    async def query_document(self, user_id: UUID, query: str) -> str:
        """Perform document-grounded question answering over the user's PDFs."""
        selection = await self._select_documents(user_id, query)
        if not selection.documents:
            return "I don't see an uploaded report yet."

        if selection.comparison and len(selection.documents) < 2:
            return "I can compare reports, but I only see one uploaded report. Upload the second report or tell me which two reports to compare."

        query_vector = await gemini_client.generate_embedding(query)
        document_ids = [doc.id for doc in selection.documents]
        matching_chunks = await self.doc_repo.search_chunks(
            user_id=user_id,
            query_vector=query_vector,
            limit=8 if selection.comparison else 5,
            document_ids=document_ids,
        )
        if not matching_chunks:
            return "I couldn't find that information in the uploaded report."

        document_lookup = {doc.id: doc for doc in selection.documents}
        context, citations = self._build_context(matching_chunks, document_lookup)
        if not context.strip():
            return "I couldn't find that information in the uploaded report."

        prompt = (
            f"Document Context:\n{context}\n\n"
            f"User Question: {query}\n\n"
            "Answer only from the provided document context. "
            "If the question asks for a comparison, compare the relevant reports directly. "
            "If the answer is not present, say you could not find that information in the uploaded report."
        )

        answer = await gemini_client.generate_response(prompt, system_instruction=DOCUMENT_SYSTEM_PROMPT)
        if "I couldn't find that information in the uploaded report" in answer:
            return answer
        if citations and "source:" not in answer.lower():
            answer = f"{answer}\n\nSource: {citations}"
        return answer

