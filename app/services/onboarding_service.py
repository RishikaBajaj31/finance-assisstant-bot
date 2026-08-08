"""Conversational onboarding extraction and persistence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.database.repositories.user_repo import UserRepository
from app.database.repositories.watchlist_repo import WatchlistRepository
from app.integrations.gemini import gemini_client
from app.services.company_resolution import company_resolver
from app.prompts.onboarding import ONBOARDING_EXTRACTION_SYSTEM_PROMPT


DEFAULT_BRIEFING_TIME = "08:00"
DEFAULT_TIMEZONE = "UTC"


@dataclass
class OnboardingExtraction:
    role: Optional[str]
    companies: List[str]
    sectors: List[str]
    interests: List[str]
    briefing_time: Optional[str]
    timezone: Optional[str]
    skip: bool
    complete: bool


def _normalize_time(value: str) -> Optional[str]:
    text = value.strip().lower()
    if not text:
        return None
    match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = match.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        return f"{hour:02d}:{minute:02d}"
    return None


def _contains_any(text: str, phrases: List[str]) -> bool:
    normalized = re.sub(r"[-_]+", " ", text.lower())
    return any(phrase in normalized for phrase in phrases)


def _heuristic_role(text: str) -> Optional[str]:
    normalized = re.sub(r"[-_]+", " ", text.lower())
    if _contains_any(text, ["fresher", "fresh graduate", "new graduate", "recent graduate", "recent grad", "new grad", "entry level", "beginner", "graduate"]):
        return "fresher"
    if _contains_any(text, ["student", "undergraduate"]):
        return "student"
    for candidate in ("financial analyst", "analyst", "investor", "founder", "finance professional", "business"):
        if candidate in normalized:
            return candidate
    return None


def _heuristic_extract(text: str) -> OnboardingExtraction:
    lowered = text.lower()
    role = _heuristic_role(text)

    companies: List[str] = []
    for name in ("nvidia", "amd", "apple", "microsoft", "tesla", "alphabet", "google", "amazon", "tsmc"):
        if name in lowered:
            companies.append(name)

    sectors: List[str] = []
    for sector in ("ai", "artificial intelligence", "semiconductors", "technology", "healthcare", "fintech", "energy", "cloud", "software"):
        if sector in lowered:
            sectors.append(sector.title() if sector != "ai" else "AI")

    interests: List[str] = []
    for interest in ("company news", "earnings", "filings", "macro events", "market moves", "valuation", "financial performance"):
        if interest in lowered:
            interests.append(interest.title())

    briefing_time = _normalize_time(text)
    timezone = None
    if "india" in lowered or "ist" in lowered:
        timezone = "Asia/Kolkata"
    elif "utc" in lowered:
        timezone = "UTC"
    elif "est" in lowered:
        timezone = "America/New_York"

    skip = any(phrase in lowered for phrase in ("just get started", "skip", "no thanks", "not now"))
    return OnboardingExtraction(
        role=role,
        companies=companies,
        sectors=sectors,
        interests=interests,
        briefing_time=briefing_time,
        timezone=timezone,
        skip=skip,
        complete=skip,
    )


class OnboardingService:
    def __init__(self, session):
        self.session = session
        self.user_repo = UserRepository(session)
        self.watch_repo = WatchlistRepository(session)

    async def extract(self, text: str, user_context: Dict[str, Any]) -> OnboardingExtraction:
        payload = {
            "message": text,
            "known_profile": user_context,
        }
        parsed = await gemini_client.generate_json(
            prompt=f"Extract onboarding data from this JSON input:\n{json.dumps(payload, ensure_ascii=True)}",
            system_instruction=ONBOARDING_EXTRACTION_SYSTEM_PROMPT,
            default={},
        )
        heuristic = _heuristic_extract(text)
        if not parsed:
            return heuristic

        extraction = OnboardingExtraction(
            role=(parsed.get("role") or None),
            companies=[c for c in parsed.get("companies", []) if c],
            sectors=[s for s in parsed.get("sectors", []) if s],
            interests=[i for i in parsed.get("interests", []) if i],
            briefing_time=(parsed.get("briefing_time") or None),
            timezone=(parsed.get("timezone") or None),
            skip=bool(parsed.get("skip")),
            complete=bool(parsed.get("complete")),
        )
        if extraction.skip and not any([extraction.role, extraction.companies, extraction.sectors, extraction.interests, extraction.briefing_time, extraction.timezone]):
            return heuristic
        if not extraction.role:
            extraction.role = heuristic.role
        if not extraction.companies:
            extraction.companies = heuristic.companies
        if not extraction.sectors:
            extraction.sectors = heuristic.sectors
        if not extraction.interests:
            extraction.interests = heuristic.interests
        if not extraction.briefing_time:
            extraction.briefing_time = heuristic.briefing_time
        if not extraction.timezone:
            extraction.timezone = heuristic.timezone
        extraction.skip = extraction.skip or heuristic.skip
        return extraction

    def _has_explicit_briefing_time(self, user, extraction: OnboardingExtraction) -> bool:
        briefing_time = getattr(user, "briefing_time", None)
        return bool(extraction.briefing_time or (briefing_time and briefing_time != DEFAULT_BRIEFING_TIME))

    def _has_explicit_timezone(self, user, extraction: OnboardingExtraction) -> bool:
        timezone = getattr(user, "timezone", None)
        return bool(extraction.timezone or (timezone and timezone != DEFAULT_TIMEZONE))

    def _missing_fields(self, user, extraction: OnboardingExtraction) -> List[str]:
        preferences = getattr(user, "preferences", None)
        known_role = bool(getattr(user, "role", None) or extraction.role)
        known_companies = bool((preferences and getattr(preferences, "interests", None)) or extraction.companies)
        known_sectors = bool((preferences and getattr(preferences, "sectors", None)) or extraction.sectors)
        known_time = self._has_explicit_briefing_time(user, extraction)
        known_tz = self._has_explicit_timezone(user, extraction)
        missing: List[str] = []
        if not known_role:
            missing.append("role")
        if not known_companies and not known_sectors:
            missing.append("focus")
        if not known_time:
            missing.append("briefing_time")
        if not known_tz:
            missing.append("timezone")
        return missing

    async def apply(self, user, extraction: OnboardingExtraction):
        if extraction.skip:
            updated = await self.user_repo.update_user_profile(user.id, onboarding_complete=True)
            return updated, True

        if extraction.role or extraction.briefing_time or extraction.timezone:
            user = await self.user_repo.update_user_profile(
                user.id,
                role=extraction.role if extraction.role else None,
                briefing_time=extraction.briefing_time if extraction.briefing_time else None,
                timezone=extraction.timezone if extraction.timezone else None,
            )

        if extraction.sectors or extraction.interests:
            await self.user_repo.upsert_preferences(user.id, sectors=extraction.sectors or None, interests=extraction.interests or None)

        resolved_companies = company_resolver.resolve_many(extraction.companies)
        for company in resolved_companies:
            await self.watch_repo.add_or_update_ticker(user.id, company.ticker, company.company_name)

        current_user = await self.user_repo.get_by_id(user.id)
        preferences = getattr(current_user, "preferences", None)
        role_known = bool(current_user and current_user.role)
        focus_known = bool(preferences and (preferences.sectors or preferences.interests or resolved_companies))
        time_known = self._has_explicit_briefing_time(current_user, extraction)
        tz_known = self._has_explicit_timezone(current_user, extraction)
        is_complete = bool(role_known and focus_known and time_known and tz_known)
        if extraction.complete:
            is_complete = True
        await self.user_repo.update_user_profile(user.id, onboarding_complete=is_complete)
        current_user = await self.user_repo.get_by_id(user.id)
        return current_user, is_complete

    def next_question(self, user, extraction: OnboardingExtraction, is_complete: bool) -> str:
        if is_complete:
            return "Perfect. I have your preferences saved, and I will tailor things from here."

        preferences = getattr(user, "preferences", None)
        role_known = bool(getattr(user, "role", None) or extraction.role)
        companies_known = bool((preferences and preferences.interests) or extraction.companies)
        sectors_known = bool((preferences and preferences.sectors) or extraction.sectors)
        time_known = self._has_explicit_briefing_time(user, extraction)
        tz_known = self._has_explicit_timezone(user, extraction)

        if not role_known:
            return "Got it. What best describes your role or background?"
        if not (companies_known or sectors_known):
            return "Which companies or sectors do you follow most closely?"
        if not time_known:
            return "What time would you like your daily briefing?"
        if not tz_known:
            return "Which timezone should I use for your briefings?"
        return "Anything else you want me to keep an eye on?"

    async def handle(self, user, text: str) -> str:
        current_user = await self.user_repo.get_by_id(user.id)
        context = {
            "role": getattr(current_user, "role", None),
            "briefing_time": getattr(current_user, "briefing_time", None),
            "timezone": getattr(current_user, "timezone", None),
            "sectors": list(getattr(getattr(current_user, "preferences", None), "sectors", []) or []),
            "interests": list(getattr(getattr(current_user, "preferences", None), "interests", []) or []),
        }
        extraction = await self.extract(text, context)
        if extraction.skip:
            await self.apply(user, extraction)
            return "No problem. We can skip the formal setup and start from here."

        updated_user, is_complete = await self.apply(user, extraction)
        if is_complete:
            return "Perfect. I have the basics down and I will keep learning as we go."

        next_question = self.next_question(updated_user, extraction, is_complete)
        if extraction.role:
            return f"Got it. {next_question}"
        return next_question
