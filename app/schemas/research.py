"""Pydantic schemas for Financial Research and News."""

from typing import List, Optional
from pydantic import BaseModel


class ResearchRequest(BaseModel):
    query: str
    tickers: Optional[List[str]] = []


class FinancialMetrics(BaseModel):
    ticker: str
    name: str
    price: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    revenue_growth: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None


class NewsItem(BaseModel):
    title: str
    source: str
    url: str
    published_at: str
    summary: str
    why_it_matters: str
    impact: str


class ResearchResponse(BaseModel):
    summary: str
    business_overview: str
    financials: str
    growth: str
    recent_news: List[NewsItem]
    risks: str
    investment_verdict: str
