"""Company and ticker resolution helpers."""

from dataclasses import dataclass
import re
from typing import Iterable, Optional

import yfinance as yf


COMMON_COMPANY_ALIASES = {
    "nvidia": "NVDA",
    "apple": "AAPL",
    "microsoft": "MSFT",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "taiwan semiconductor": "TSM",
    "tsmc": "TSM",
    "meta": "META",
    "facebook": "META",
    "amd": "AMD",
    "advanced micro devices": "AMD",
    "intel": "INTC",
    "oracle": "ORCL",
    "broadcom": "AVGO",
    "qualcomm": "QCOM",
    "netflix": "NFLX",
    "adobe": "ADBE",
    "salesforce": "CRM",
    "palantir": "PLTR",
    "uber": "UBER",
    "shopify": "SHOP",
    "pfizer": "PFE",
    "moderna": "MRNA",
    "bank of america": "BAC",
    "jpmorgan": "JPM",
    "jpmorgan chase": "JPM",
    "visa": "V",
    "mastercard": "MA",
    "costco": "COST",
    "walmart": "WMT",
    "coca cola": "KO",
    "pepsico": "PEP",
    "boeing": "BA",
    "caterpillar": "CAT",
}


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _looks_like_ticker(value: str) -> bool:
    value = value.strip().upper()
    return bool(re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,4}", value))


def _validate_symbol(symbol: str) -> bool:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info if hasattr(ticker, "fast_info") else {}
        if info:
            return True
        data = ticker.info or {}
        return bool(data.get("shortName") or data.get("longName") or data.get("currentPrice") or data.get("marketCap"))
    except Exception:
        return False


@dataclass
class CompanyResolution:
    company_name: str
    ticker: str
    confidence: float = 1.0


class CompanyResolver:
    """Resolve company names to tickers using aliases and Yahoo Finance search."""

    def resolve(self, reference: str) -> Optional[CompanyResolution]:
        raw = reference.strip()
        if not raw:
            return None

        maybe_ticker = raw.upper().replace(".", "-")
        if _looks_like_ticker(maybe_ticker) and _validate_symbol(maybe_ticker):
            return CompanyResolution(company_name=raw, ticker=maybe_ticker, confidence=0.95)

        normalized = _normalize(raw)
        for alias, ticker in COMMON_COMPANY_ALIASES.items():
            if alias == normalized or alias in normalized or normalized in alias:
                if _validate_symbol(ticker):
                    return CompanyResolution(company_name=raw, ticker=ticker, confidence=0.9)

        try:
            search = yf.Search(raw)
            quotes = getattr(search, "quotes", []) or []
            for quote in quotes:
                symbol = (quote.get("symbol") or "").upper()
                if not symbol:
                    continue
                if _validate_symbol(symbol):
                    name = quote.get("longname") or quote.get("shortname") or raw
                    return CompanyResolution(company_name=name, ticker=symbol, confidence=0.75)
        except Exception:
            pass

        return None

    def resolve_many(self, references: Iterable[str]) -> list[CompanyResolution]:
        results: list[CompanyResolution] = []
        seen: set[str] = set()
        for ref in references:
            resolved = self.resolve(ref)
            if resolved and resolved.ticker not in seen:
                seen.add(resolved.ticker)
                results.append(resolved)
        return results


company_resolver = CompanyResolver()
