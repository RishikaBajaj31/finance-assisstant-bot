"""Conversational watchlist management service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from app.database.repositories.watchlist_repo import WatchlistRepository
from app.integrations.gemini import gemini_client
from app.integrations.yfinance_client import yfinance_client
from app.prompts.watchlist import WATCHLIST_EXTRACTION_SYSTEM_PROMPT
from app.services.company_resolution import company_resolver
from app.services.news_service import news_service


@dataclass
class WatchlistExtraction:
    action: str
    companies: List[str]
    tickers: List[str]
    skip: bool = False


class WatchlistService:
    def __init__(self, session):
        self.session = session
        self.repo = WatchlistRepository(session)

    async def extract(self, text: str) -> WatchlistExtraction:
        parsed = await gemini_client.generate_json(
            prompt=f"Extract watchlist request from this JSON payload:\n{json.dumps({'message': text}, ensure_ascii=True)}",
            system_instruction=WATCHLIST_EXTRACTION_SYSTEM_PROMPT,
            default={},
        )
        if not parsed:
            lowered = text.lower()
            if any(phrase in lowered for phrase in ("what am i watching", "show me my watchlist", "list my watchlist")):
                return WatchlistExtraction(action="list", companies=[], tickers=[])
            if any(phrase in lowered for phrase in ("what's happening with", "what is happening with", "watchlist update")):
                return WatchlistExtraction(action="summary", companies=[], tickers=[])
            if any(verb in lowered for verb in ("remove", "delete", "stop tracking", "unwatch")):
                return WatchlistExtraction(action="remove", companies=[], tickers=[])
            return WatchlistExtraction(action="add", companies=[], tickers=[])

        return WatchlistExtraction(
            action=(parsed.get("action") or "unknown"),
            companies=[c for c in parsed.get("companies", []) if c],
            tickers=[t for t in parsed.get("tickers", []) if t],
            skip=bool(parsed.get("skip")),
        )

    async def _resolved_items(self, companies: Iterable[str], tickers: Iterable[str]) -> list[tuple[str, str]]:
        resolved: list[tuple[str, str]] = []
        for ticker in tickers:
            resolved.append((ticker.upper(), ticker.upper()))
        for company in companies:
            result = company_resolver.resolve(company)
            if result:
                resolved.append((result.ticker, result.company_name))
        deduped: list[tuple[str, str]] = []
        seen: set[str] = set()
        for ticker, company_name in resolved:
            if ticker not in seen:
                seen.add(ticker)
                deduped.append((ticker, company_name))
        return deduped

    async def add_items(self, user_id, companies: Iterable[str], tickers: Iterable[str]) -> tuple[list[str], list[str]]:
        resolved = await self._resolved_items(companies, tickers)
        added: list[str] = []
        unresolved: list[str] = []
        for ticker, company_name in resolved:
            existing = await self.repo.get_by_ticker(user_id, ticker)
            if existing:
                continue
            await self.repo.add_ticker(user_id, ticker, company_name)
            added.append(f"{company_name} ({ticker})")
        return added, unresolved

    async def remove_items(self, user_id, companies: Iterable[str], tickers: Iterable[str]) -> list[str]:
        resolved = await self._resolved_items(companies, tickers)
        removed: list[str] = []
        for ticker, company_name in resolved:
            if await self.repo.remove_ticker(user_id, ticker):
                removed.append(f"{company_name} ({ticker})")
        return removed

    async def list_items(self, user_id) -> str:
        items = await self.repo.get_user_watchlist(user_id)
        if not items:
            return "Your watchlist is empty right now."
        lines = [f"• {item.company_name or item.ticker} ({item.ticker})" for item in items]
        return "Here is what you are watching:\n" + "\n".join(lines)

    async def summary(self, user_id) -> str:
        items = await self.repo.get_user_watchlist(user_id)
        if not items:
            return "Your watchlist is empty right now."

        summaries: list[str] = []
        for item in items[:5]:
            news_items = yfinance_client.get_recent_news(item.ticker, limit=2)
            if news_items:
                top = news_items[0]
                summaries.append(f"{item.ticker}: {top.get('title', 'Recent activity')}")
            else:
                summaries.append(f"{item.ticker}: No major recent headlines I could verify.")
        if not summaries:
            return "I could not find anything notable on your watchlist right now."

        if not getattr(gemini_client, "client", None):
            return "Here is the latest from your watchlist:\n" + "\n".join(f"- {item}" for item in summaries)

        prompt = (
            "Summarize the following watchlist updates in a concise, analyst-style format with what matters most and why.\n"
            f"{summaries}"
        )
        return await gemini_client.generate_response(prompt)

    async def handle(self, user_id, text: str) -> tuple[str, bool]:
        extraction = await self.extract(text)
        if extraction.skip:
            return "No problem.", True

        if extraction.action in ("list", "show"):
            return await self.list_items(user_id), True

        if extraction.action == "summary":
            return await self.summary(user_id), True

        if extraction.action == "remove":
            removed = await self.remove_items(user_id, extraction.companies, extraction.tickers)
            if not removed:
                return "I could not find anything to remove from your watchlist.", True
            return "Done. I removed " + ", ".join(removed) + " from your watchlist.", True

        resolved = await self._resolved_items(extraction.companies, extraction.tickers)
        if not resolved:
            return "Which company should I track for you?", False
        added, _ = await self.add_items(user_id, extraction.companies, extraction.tickers)
        if not added:
            return "That is already on your watchlist.", True
        return "Done - " + ", ".join(added) + " is now on your watchlist.", True
