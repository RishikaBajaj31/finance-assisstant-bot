"""Smart alert extraction, management, and evaluation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from app.core.constants import (
    ALERT_ACTION_CANCEL,
    ALERT_ACTION_CREATE,
    ALERT_ACTION_LIST,
    ALERT_ACTION_UPDATE,
    ALERT_SCOPE_TICKER,
    ALERT_SCOPE_WATCHLIST,
    ALERT_TYPE_EARNINGS,
    ALERT_TYPE_NEWS,
    ALERT_TYPE_PERCENT,
    ALERT_TYPE_PRICE,
)
from app.core.logging import logger
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.watchlist_repo import AlertRepository, WatchlistRepository
from app.integrations.gemini import gemini_client
from app.integrations.news_client import news_client
from app.integrations.yfinance_client import yfinance_client
from app.prompts.alerts import ALERT_EXTRACTION_SYSTEM_PROMPT
from app.services.company_resolution import company_resolver
from app.services.company_resolution import COMMON_COMPANY_ALIASES


NEWS_IMPORTANT_KEYWORDS = {
    "earnings": 5,
    "acquisition": 5,
    "merger": 5,
    "guidance": 5,
    "sec": 4,
    "regulatory": 4,
    "regulation": 4,
    "lawsuit": 4,
    "ceo": 3,
    "cfo": 3,
    "product": 3,
    "launch": 3,
    "announces": 3,
    "announcement": 3,
    "investment": 2,
    "partnership": 2,
}

HIGH_QUALITY_SOURCES = {"reuters", "bloomberg", "wsj", "financial times", "cnbc"}


@dataclass
class AlertExtraction:
    action: str
    alert_type: Optional[str]
    companies: List[str]
    tickers: List[str]
    condition: Optional[str]
    threshold: Optional[float]
    reminder_minutes: Optional[int]
    scope: Optional[str]
    target: Optional[str]
    skip: bool = False


def _parse_number(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def _parse_reminder_minutes(text: str) -> Optional[int]:
    lowered = text.lower()
    if "hour" in lowered:
        value = _parse_number(lowered) or 1
        return int(value * 60)
    if "minute" in lowered:
        value = _parse_number(lowered) or 30
        return int(value)
    return None


def _heuristic_extract(text: str) -> AlertExtraction:
    lowered = text.lower()
    action = ALERT_ACTION_CREATE
    if any(phrase in lowered for phrase in ("what alerts do i have", "show my alerts", "list my alerts")):
        action = ALERT_ACTION_LIST
    elif any(phrase in lowered for phrase in ("cancel", "remove", "delete", "stop tracking", "turn off")):
        action = ALERT_ACTION_CANCEL
    elif any(phrase in lowered for phrase in ("update", "change", "edit")):
        action = ALERT_ACTION_UPDATE

    if action == ALERT_ACTION_LIST:
        return AlertExtraction(action, None, [], [], None, None, None, None, None, False)

    alert_type: Optional[str] = None
    if any(phrase in lowered for phrase in ("earnings", "earnings call", "before")):
        alert_type = ALERT_TYPE_EARNINGS
    elif "%" in lowered or "percent" in lowered or "percentage" in lowered:
        alert_type = ALERT_TYPE_PERCENT
    elif any(phrase in lowered for phrase in ("major news", "major announcement", "anything major", "important news", "big news")):
        alert_type = ALERT_TYPE_NEWS
    elif any(phrase in lowered for phrase in ("below", "under", "drops", "falls", "less than", "above", "over", "crosses", "goes to", "hits")):
        alert_type = ALERT_TYPE_PRICE

    scope = ALERT_SCOPE_WATCHLIST if "companies i'm watching" in lowered or "companies im watching" in lowered else ALERT_SCOPE_TICKER

    companies: List[str] = []
    for name in COMMON_COMPANY_ALIASES:
        if name in lowered:
            companies.append(name)

    tickers = [m.upper() for m in re.findall(r"\b[A-Z]{2,5}\b", text)]
    threshold = _parse_number(lowered)
    reminder_minutes = _parse_reminder_minutes(lowered)

    condition = None
    if alert_type == ALERT_TYPE_PRICE:
        if any(phrase in lowered for phrase in ("below", "under", "drops", "falls", "less than")):
            condition = "price_below"
        else:
            condition = "price_above"
    elif alert_type == ALERT_TYPE_PERCENT:
        condition = "percent_move_gt"
    elif alert_type == ALERT_TYPE_EARNINGS:
        condition = "earnings_reminder"
    elif alert_type == ALERT_TYPE_NEWS:
        condition = "major_news"

    if alert_type == ALERT_TYPE_EARNINGS and reminder_minutes is None:
        reminder_minutes = 60

    target = None
    if tickers:
        target = tickers[0]

    return AlertExtraction(action, alert_type, companies, tickers, condition, threshold, reminder_minutes, scope, target, False)


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _format_company_list(items: Iterable[str]) -> str:
    return ", ".join(items)


class AlertService:
    def __init__(self, session):
        self.session = session
        self.alert_repo = AlertRepository(session)
        self.user_repo = UserRepository(session)
        self.watch_repo = WatchlistRepository(session)

    async def extract(self, text: str, user_context: Optional[Dict[str, Any]] = None) -> AlertExtraction:
        user_context = user_context or {}
        parsed = await gemini_client.generate_json(
            prompt=(
                "Extract alert request from this JSON payload:\n"
                f"{json.dumps({'message': text, 'user_context': user_context}, ensure_ascii=True)}"
            ),
            system_instruction=ALERT_EXTRACTION_SYSTEM_PROMPT,
            default={},
        )
        if not parsed:
            return _heuristic_extract(text)

        action = str(parsed.get("action") or ALERT_ACTION_CREATE)
        alert_type = parsed.get("alert_type") or None
        companies = [c for c in parsed.get("companies", []) if c]
        tickers = [t for t in parsed.get("tickers", []) if t]
        condition = parsed.get("condition") or None
        threshold = parsed.get("threshold")
        reminder_minutes = parsed.get("reminder_minutes")
        scope = parsed.get("scope") or None
        target = parsed.get("target") or None
        if alert_type is None and action == ALERT_ACTION_CREATE:
            alert_type = ALERT_TYPE_PRICE
        return AlertExtraction(
            action=action,
            alert_type=alert_type,
            companies=companies,
            tickers=[t.upper() for t in tickers],
            condition=condition,
            threshold=float(threshold) if threshold is not None else None,
            reminder_minutes=int(reminder_minutes) if reminder_minutes is not None else None,
            scope=scope,
            target=target,
            skip=bool(parsed.get("skip")),
        )

    async def _resolve_targets(self, extraction: AlertExtraction, user_id: UUID) -> list[tuple[str, str]]:
        resolved: list[tuple[str, str]] = []
        for ticker in extraction.tickers:
            result = company_resolver.resolve(ticker)
            if result:
                resolved.append((result.ticker, result.company_name))
        if extraction.companies:
            for company in extraction.companies:
                result = company_resolver.resolve(company)
                if result:
                    resolved.append((result.ticker, result.company_name))
        if extraction.scope == ALERT_SCOPE_WATCHLIST and not resolved:
            items = await self.watch_repo.get_user_watchlist(user_id)
            for item in items:
                resolved.append((item.ticker, item.company_name or item.ticker))
        deduped: list[tuple[str, str]] = []
        seen: set[str] = set()
        for ticker, company_name in resolved:
            if ticker not in seen:
                seen.add(ticker)
                deduped.append((ticker, company_name))
        return deduped

    async def _create_alert(self, user_id: UUID, extraction: AlertExtraction, ticker: Optional[str], company_name: Optional[str]) -> Optional[str]:
        alert_type = extraction.alert_type or ALERT_TYPE_PRICE
        scope = extraction.scope or ALERT_SCOPE_TICKER
        condition = extraction.condition
        threshold = extraction.threshold
        reminder_minutes = extraction.reminder_minutes
        title = company_name or ticker
        details = None
        reminder_at_utc = None
        event_at_utc = None

        if alert_type == ALERT_TYPE_EARNINGS:
            if not ticker:
                return None
            event_at_utc = yfinance_client.get_next_earnings_datetime(ticker)
            if not event_at_utc:
                return "I couldn't verify the next earnings date right now."
            reminder_minutes = reminder_minutes or 60
            reminder_at_utc = event_at_utc - timedelta(minutes=reminder_minutes)
            title = f"{company_name or ticker} earnings"
            condition = "earnings_reminder"
        elif alert_type == ALERT_TYPE_PERCENT:
            if threshold is None:
                threshold = 5.0
            condition = condition or "percent_move_gt"
        elif alert_type == ALERT_TYPE_NEWS:
            condition = "major_news"
        else:
            if threshold is None:
                return "Which price level should I use?"
            condition = condition or ("price_below" if "below" in (extraction.condition or "") else "price_above")

        duplicate = await self.alert_repo.find_duplicate(
            user_id=user_id,
            alert_type=alert_type,
            ticker=ticker,
            condition=condition,
            threshold=threshold,
            reminder_minutes=reminder_minutes,
            scope=scope,
            title=title,
        )
        if duplicate:
            return f"That alert is already active for {company_name or ticker}."

        await self.alert_repo.create_alert(
            user_id=user_id,
            ticker=ticker,
            condition=condition,
            threshold=threshold,
            alert_type=alert_type,
            operator="lt" if condition in ("price_below", "<", "<=") else "gt" if condition in ("price_above", ">", ">=") else None,
            reminder_minutes=reminder_minutes,
            scope=scope,
            title=title,
            details=details,
            reminder_at_utc=reminder_at_utc,
            event_at_utc=event_at_utc,
        )

        if alert_type == ALERT_TYPE_PRICE:
            operator_text = "falls below" if condition in ("price_below", "<", "<=") else "rises above"
            return f"Done. I'll alert you if {company_name or ticker} ({ticker}) {operator_text} ${threshold:.2f}."
        if alert_type == ALERT_TYPE_PERCENT:
            return f"Done. I'll notify you if {company_name or ticker} ({ticker}) moves more than {threshold:.0f}% in a day."
        if alert_type == ALERT_TYPE_EARNINGS:
            return f"Got it. I'll remind you before {company_name or ticker}'s next earnings event."
        if alert_type == ALERT_TYPE_NEWS:
            return f"Done. I'll watch {company_name or ticker} for major news."
        return f"Done. I set up an alert for {company_name or ticker}."

    async def list_alerts(self, user_id: UUID) -> str:
        alerts = await self.alert_repo.get_user_active_alerts(user_id)
        if not alerts:
            return "You do not have any active alerts right now."
        lines: list[str] = []
        for alert in alerts[:10]:
            label = alert.title or alert.ticker or alert.alert_type
            if alert.alert_type == ALERT_TYPE_PRICE:
                lines.append(f"- {label}: {alert.condition} ${alert.threshold:.2f}")
            elif alert.alert_type == ALERT_TYPE_PERCENT:
                lines.append(f"- {label}: move more than {alert.threshold:.0f}%")
            elif alert.alert_type == ALERT_TYPE_EARNINGS:
                lines.append(f"- {label}: reminder {alert.reminder_minutes or 60} minutes before earnings")
            elif alert.alert_type == ALERT_TYPE_NEWS:
                lines.append(f"- {label}: major news monitoring")
            else:
                lines.append(f"- {label}")
        return "Here are your active alerts:\n" + "\n".join(lines)

    async def cancel_alerts(self, user_id: UUID, extraction: AlertExtraction) -> str:
        if not extraction.tickers and not extraction.companies and extraction.scope != ALERT_SCOPE_WATCHLIST:
            cancelled = await self.alert_repo.cancel_all(user_id)
            if cancelled:
                return "Done. I turned off all of your alerts."
            return "You did not have any active alerts to cancel."

        resolved = await self._resolve_targets(extraction, user_id)
        if extraction.scope == ALERT_SCOPE_WATCHLIST and not resolved:
            cancelled = await self.alert_repo.cancel_all(user_id)
            if cancelled:
                return "Done. I turned off all of your alerts."
            return "You did not have any active alerts to cancel."

        cancelled_labels: list[str] = []
        for ticker, company_name in resolved:
            count = await self.alert_repo.cancel_by_ticker(user_id, ticker)
            if count:
                cancelled_labels.append(f"{company_name or ticker} ({ticker})")
        if not cancelled_labels:
            return "I could not find an active alert to cancel."
        return "Done. I cancelled " + ", ".join(cancelled_labels) + "."

    async def handle(self, user, text: str) -> str:
        user_context = {
            "timezone": getattr(user, "timezone", None),
            "briefing_time": getattr(user, "briefing_time", None),
            "role": getattr(user, "role", None),
        }
        extraction = await self.extract(text, user_context=user_context)
        if extraction.skip:
            return "No problem."
        if extraction.action == ALERT_ACTION_LIST:
            return await self.list_alerts(user.id)
        if extraction.action == ALERT_ACTION_CANCEL:
            return await self.cancel_alerts(user.id, extraction)
        if extraction.action == ALERT_ACTION_UPDATE:
            resolved = await self._resolve_targets(extraction, user.id)
            if resolved:
                for ticker, _ in resolved:
                    await self.alert_repo.cancel_by_ticker(user.id, ticker)

        resolved = await self._resolve_targets(extraction, user.id)
        if extraction.alert_type == ALERT_TYPE_NEWS and extraction.scope == ALERT_SCOPE_WATCHLIST:
            if not resolved:
                watchlist = await self.watch_repo.get_user_watchlist(user.id)
                if not watchlist:
                    return "Your watchlist is empty right now. Add companies first, then I can watch for major news."
                for item in watchlist:
                    resolved.append((item.ticker, item.company_name or item.ticker))

        if extraction.alert_type in (ALERT_TYPE_PRICE, ALERT_TYPE_PERCENT, ALERT_TYPE_EARNINGS, ALERT_TYPE_NEWS):
            if not resolved and extraction.scope != ALERT_SCOPE_WATCHLIST:
                return "Which company do you mean?"

        if extraction.alert_type == ALERT_TYPE_NEWS and extraction.scope == ALERT_SCOPE_WATCHLIST and not resolved:
            return "Your watchlist is empty right now. Add companies first, then I can watch for major news."

        if extraction.alert_type == ALERT_TYPE_NEWS and extraction.scope == ALERT_SCOPE_WATCHLIST:
            message = await self._create_alert(user.id, extraction, None, "Your watchlist")
            return message or "Done. I will monitor your watchlist for major news."

        if not resolved:
            return "Which company do you mean?"

        created_messages: list[str] = []
        for ticker, company_name in resolved[:5]:
            message = await self._create_alert(user.id, extraction, ticker, company_name)
            if message:
                created_messages.append(message)
        if not created_messages:
            return "I could not create that alert."
        if len(created_messages) == 1:
            return created_messages[0]
        return "Done. " + " ".join(created_messages)

    async def _evaluate_price_alert(self, alert) -> Optional[Dict[str, Any]]:
        if not alert.ticker or alert.threshold is None:
            return None
        info = yfinance_client.get_ticker_info(alert.ticker)
        current_price = float(info.get("current_price") or 0.0)
        condition = (alert.condition or "").lower()
        triggered = False
        if condition in ("price_above", "above", ">", ">="):
            triggered = current_price >= float(alert.threshold)
        elif condition in ("price_below", "below", "<", "<="):
            triggered = current_price <= float(alert.threshold)
        if not triggered:
            return None
        return {
            "ticker": alert.ticker,
            "current_price": current_price,
            "threshold": float(alert.threshold),
            "condition": condition,
            "company_name": info.get("name") or alert.ticker,
        }

    async def _evaluate_percent_alert(self, alert) -> Optional[Dict[str, Any]]:
        if not alert.ticker or alert.threshold is None:
            return None
        move_pct = yfinance_client.get_daily_move_pct(alert.ticker)
        if abs(move_pct) < float(alert.threshold):
            return None
        info = yfinance_client.get_ticker_info(alert.ticker)
        return {
            "ticker": alert.ticker,
            "move_pct": move_pct,
            "threshold": float(alert.threshold),
            "company_name": info.get("name") or alert.ticker,
        }

    async def _evaluate_earnings_alert(self, alert) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc)
        if not alert.reminder_at_utc or alert.triggered or alert.reminder_at_utc > now:
            return None
        info = yfinance_client.get_ticker_info(alert.ticker or "")
        return {
            "ticker": alert.ticker,
            "company_name": info.get("name") or alert.title or alert.ticker,
            "event_at_utc": alert.event_at_utc,
            "reminder_minutes": alert.reminder_minutes or 60,
        }

    def _score_news_article(self, article: Dict[str, Any], ticker: str) -> int:
        text = " ".join(
            [
                str(article.get("title", "")),
                str(article.get("summary", "")),
                str(article.get("source", "")),
            ]
        ).lower()
        score = 0
        for keyword, weight in NEWS_IMPORTANT_KEYWORDS.items():
            if keyword in text:
                score += weight
        if any(source in text for source in HIGH_QUALITY_SOURCES):
            score += 2
        if ticker.lower() in text:
            score += 2
        return score

    async def _evaluate_news_alert(self, alert) -> Optional[Dict[str, Any]]:
        tickers: list[str] = []
        if alert.scope == ALERT_SCOPE_WATCHLIST:
            watchlist = await self.watch_repo.get_user_watchlist(alert.user_id)
            tickers = [item.ticker for item in watchlist]
        elif alert.ticker:
            tickers = [alert.ticker]
        if not tickers:
            return None

        best_article = None
        best_score = 0
        best_ticker = None
        for ticker in tickers[:8]:
            if getattr(news_client, "api_key", None):
                articles = await news_client.fetch_financial_news(query=ticker, limit=5)
            else:
                raw_news = yfinance_client.get_recent_news(ticker, limit=5)
                articles = [
                    {
                        "title": item.get("title", ""),
                        "source": item.get("publisher", "Financial News"),
                        "summary": item.get("title", ""),
                        "url": item.get("link", "#"),
                    }
                    for item in raw_news
                ]
            for article in articles:
                score = self._score_news_article(article, ticker)
                if score > best_score:
                    best_score = score
                    best_article = article
                    best_ticker = ticker

        if not best_article or best_score < 5:
            return None
        return {
            "ticker": best_ticker,
            "article": best_article,
            "score": best_score,
        }

    def _build_notification(self, alert, payload: Dict[str, Any], user_timezone: Optional[str] = None) -> str:
        label = alert.title or alert.ticker or "Alert"
        if alert.alert_type == ALERT_TYPE_PRICE:
            return (
                f"**{label} Alert**\n\n"
                f"{payload['ticker']} is currently at ${payload['current_price']:.2f}.\n\n"
                f"Your threshold:\n"
                f"{'Below' if (payload['condition'] in ('price_below', 'below', '<', '<=')) else 'Above'} ${payload['threshold']:.2f}\n\n"
                "The alert has been triggered."
            )
        if alert.alert_type == ALERT_TYPE_PERCENT:
            direction = "up" if payload["move_pct"] >= 0 else "down"
            return (
                f"**{label} Alert**\n\n"
                f"{payload['ticker']} is {direction} {abs(payload['move_pct']):.1f}% today.\n\n"
                f"Your alert:\n"
                f"Move > {payload['threshold']:.0f}%\n\n"
                f"Triggered at approximately {abs(payload['move_pct']):.1f}%."
            )
        if alert.alert_type == ALERT_TYPE_EARNINGS:
            reminder = alert.reminder_minutes or payload.get("reminder_minutes") or 60
            return (
                f"**{label} Reminder**\n\n"
                f"{payload.get('company_name') or payload.get('ticker') or label}'s earnings event is approaching.\n\n"
                f"Event:\n{payload.get('company_name') or payload.get('ticker') or label}\n\n"
                f"Reminder:\n{reminder} minutes before"
            )
        if alert.alert_type == ALERT_TYPE_NEWS:
            article = payload["article"]
            return (
                f"**{label} News Alert**\n\n"
                f"{article.get('title', 'Important company news')}.\n\n"
                f"Source:\n{article.get('source', 'Financial News')}\n\n"
                "The alert has been triggered."
            )
        return f"**{label}**\n\nYour alert has been triggered."

    async def evaluate_active_alerts(self) -> List[Dict[str, Any]]:
        """Evaluate all active alerts and return triggered notifications."""
        triggered_alerts: List[Dict[str, Any]] = []
        alerts = await self.alert_repo.get_active_alerts()
        now = datetime.now(timezone.utc)

        for alert in alerts:
            try:
                payload = None
                if alert.alert_type == ALERT_TYPE_PRICE:
                    payload = await self._evaluate_price_alert(alert)
                elif alert.alert_type == ALERT_TYPE_PERCENT:
                    payload = await self._evaluate_percent_alert(alert)
                elif alert.alert_type == ALERT_TYPE_EARNINGS:
                    payload = await self._evaluate_earnings_alert(alert)
                elif alert.alert_type == ALERT_TYPE_NEWS:
                    payload = await self._evaluate_news_alert(alert)

                alert.last_checked = now
                if not payload:
                    continue

                alert.triggered = True
                alert.is_active = False
                alert.triggered_at = now
                alert.last_notified_at = now

                user = await self.user_repo.get_by_id(alert.user_id)
                notification = self._build_notification(alert, payload, getattr(user, "timezone", None))
                triggered_alerts.append(
                    {
                        "alert_id": str(alert.id),
                        "user_id": str(alert.user_id),
                        "chat_id": getattr(user, "telegram_id", None),
                        "message": notification,
                        "alert_type": alert.alert_type,
                        "ticker": alert.ticker,
                        "payload": payload,
                    }
                )
            except Exception as exc:
                logger.warning("Alert evaluation failed for alert %s: %s", alert.id, exc)

        await self.session.commit()
        return triggered_alerts
