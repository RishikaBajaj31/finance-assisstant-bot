import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from app.agents.nodes.router_node import router_node
from app.agents.state import AgentState
from app.database.connection import AsyncSessionLocal, Base, engine
from app.database.migrations.ensure_schema import ensure_schema
from app.database.repositories.memory_repo import MemoryRepository
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.watchlist_repo import WatchlistRepository
from app.integrations.gemini import gemini_client
from app.main import app
from app.services.company_resolution import CompanyResolution, company_resolver
from app.services.memory_service import MemoryService
from app.services.onboarding_service import OnboardingExtraction, OnboardingService
from app.services.user_service import UserService
from app.services.watchlist_service import WatchlistExtraction, WatchlistService


TABLES = [
    "document_chunks",
    "documents",
    "research_history",
    "alerts",
    "watchlists",
    "memories",
    "conversations",
    "user_preferences",
    "users",
]


def run(coro):
    async def wrapper():
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(wrapper())


async def reset_db():
    await ensure_schema(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql(f"TRUNCATE TABLE {', '.join(TABLES)} RESTART IDENTITY CASCADE")


async def create_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        return await UserService(session).get_or_create_user(telegram_id, username="tester", full_name="Test User")


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_onboarding_extraction(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            service = OnboardingService(session)
            monkeypatch.setattr(
                gemini_client,
                "generate_json",
                AsyncMock(
                    return_value={
                        "role": "financial analyst",
                        "companies": ["NVDA", "AMD"],
                        "sectors": ["AI", "Semiconductors"],
                        "interests": ["Company News", "Earnings"],
                        "briefing_time": "08:00",
                        "timezone": "Asia/Kolkata",
                        "skip": False,
                        "complete": False,
                    }
                ),
            )
            extracted = await service.extract("I am a financial analyst and follow Nvidia.", {})
            assert extracted.role == "financial analyst"
            assert extracted.companies == ["NVDA", "AMD"]
            assert extracted.briefing_time == "08:00"

    run(scenario())


def test_first_time_user_onboarding_persists_profile(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1002, username="tester", full_name="Test User")
            service = OnboardingService(session)
            monkeypatch.setattr(
                service,
                "extract",
                AsyncMock(
                    return_value=OnboardingExtraction(
                        role="financial analyst",
                        companies=["Nvidia"],
                        sectors=["AI", "Semiconductors"],
                        interests=["Company News", "Earnings"],
                        briefing_time="08:00",
                        timezone="Asia/Kolkata",
                        skip=False,
                        complete=False,
                    )
                ),
            )
            monkeypatch.setattr(
                "app.services.onboarding_service.company_resolver.resolve_many",
                lambda refs: [CompanyResolution(company_name="Nvidia", ticker="NVDA")],
            )
            response = await service.handle(user, "I am a financial analyst.")
            refreshed = await UserRepository(session).get_by_id(user.id)
            watchlist = await WatchlistRepository(session).get_user_watchlist(user.id)

            assert "Got it" in response or "Perfect" in response
            assert refreshed.role == "financial analyst"
            assert refreshed.briefing_time == "08:00"
            assert refreshed.timezone == "Asia/Kolkata"
            assert refreshed.onboarding_complete is True
            assert watchlist and watchlist[0].ticker == "NVDA"

    run(scenario())


def test_skip_onboarding(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1003, username="tester", full_name="Test User")
            service = OnboardingService(session)
            monkeypatch.setattr(
                service,
                "extract",
                AsyncMock(
                    return_value=OnboardingExtraction(
                        role=None,
                        companies=[],
                        sectors=[],
                        interests=[],
                        briefing_time=None,
                        timezone=None,
                        skip=True,
                        complete=True,
                    )
                ),
            )
            response = await service.handle(user, "Just get started.")
            refreshed = await UserRepository(session).get_by_id(user.id)

            assert "skip" in response.lower() or "problem" in response.lower()
            assert refreshed.onboarding_complete is True

    run(scenario())


def test_existing_user_bypasses_onboarding(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1004, username="tester", full_name="Test User")
            await UserRepository(session).update_user_profile(user.id, onboarding_complete=True)
            state: AgentState = {
                "telegram_id": 1004,
                "user_id": str(user.id),
                "user_name": "Test User",
                "input_text": "Tell me about Nvidia",
                "intent": "general",
                "is_onboarded": True,
                "conversation_history": "",
                "recalled_memories": [],
                "document_id": None,
                "response": "",
                "metadata": {},
                "db_session": session,
            }
            monkeypatch.setattr(gemini_client, "generate_response", AsyncMock(return_value="general"))
            routed = await router_node(state)
            assert routed["intent"] != "onboarding"

    run(scenario())


def test_long_term_memory_creation(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1005, username="tester", full_name="Test User")
            service = MemoryService(session)
            monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.1] * 768))
            memory = await service.add_semantic_memory(user.id, "User is a financial analyst.")
            assert memory.content == "User is a financial analyst."
            assert memory.embedding is not None

    run(scenario())


def test_duplicate_memory_prevention(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1006, username="tester", full_name="Test User")
            service = MemoryService(session)
            monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.2] * 768))
            first = await service.add_semantic_memory(user.id, "User prefers concise answers.")
            second = await service.add_semantic_memory(user.id, "User prefers concise answers.")
            rows = await MemoryRepository(session).get_all_memories(user.id)
            assert first.id == second.id
            assert len(rows) == 1

    run(scenario())


def test_memory_retrieval(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1007, username="tester", full_name="Test User")
            service = MemoryService(session)
            monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.3] * 768))
            await service.add_semantic_memory(user.id, "User mainly follows AI and semiconductor companies.")
            memories = await service.recall_relevant_memories(user.id, "What should I watch this week?")
            assert memories
            assert any("AI and semiconductor" in m for m in memories)

    run(scenario())


def test_contradictory_memory_update(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1008, username="tester", full_name="Test User")
            service = MemoryService(session)
            monkeypatch.setattr(gemini_client, "generate_embedding", AsyncMock(return_value=[0.4] * 768))
            monkeypatch.setattr(
                gemini_client,
                "generate_json",
                AsyncMock(
                    side_effect=[
                        {
                            "should_remember": True,
                            "memory_type": "preference",
                            "content": "User primarily follows AI and semiconductors.",
                            "importance": 0.9,
                            "memory_key": "sector_focus",
                        },
                        {
                            "should_remember": True,
                            "memory_type": "preference",
                            "content": "User primarily follows consumer internet and cloud companies.",
                            "importance": 0.9,
                            "memory_key": "sector_focus",
                        },
                    ]
                ),
            )
            first = await service.maybe_store_memory(user.id, "I mainly follow AI and semiconductor companies.")
            second = await service.maybe_store_memory(user.id, "I now mainly follow consumer internet and cloud companies.")
            rows = await MemoryRepository(session).get_all_memories(user.id)
            assert len(rows) == 1
            assert first.id == second.id
            assert rows[0].content == "User primarily follows consumer internet and cloud companies."

    run(scenario())


def test_company_ticker_resolution(monkeypatch):
    monkeypatch.setattr("app.services.company_resolution._validate_symbol", lambda symbol: True)
    resolved = company_resolver.resolve("Nvidia")
    assert resolved.ticker == "NVDA"


def test_add_watchlist_item(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1009, username="tester", full_name="Test User")
            service = WatchlistService(session)
            monkeypatch.setattr(
                service,
                "extract",
                AsyncMock(return_value=WatchlistExtraction(action="add", companies=["Nvidia"], tickers=[])),
            )
            monkeypatch.setattr(
                "app.services.watchlist_service.company_resolver.resolve",
                lambda company: CompanyResolution(company_name=company, ticker="NVDA"),
            )
            response, _ = await service.handle(user.id, "Add Nvidia to my watchlist.")
            rows = await WatchlistRepository(session).get_user_watchlist(user.id)
            assert "NVDA" in response
            assert rows[0].ticker == "NVDA"

    run(scenario())


def test_duplicate_watchlist_item(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1010, username="tester", full_name="Test User")
            service = WatchlistService(session)
            monkeypatch.setattr(
                service,
                "extract",
                AsyncMock(return_value=WatchlistExtraction(action="add", companies=["Nvidia"], tickers=[])),
            )
            monkeypatch.setattr(
                "app.services.watchlist_service.company_resolver.resolve",
                lambda company: CompanyResolution(company_name=company, ticker="NVDA"),
            )
            first, _ = await service.handle(user.id, "Add Nvidia to my watchlist.")
            second, _ = await service.handle(user.id, "Add Nvidia to my watchlist.")
            rows = await WatchlistRepository(session).get_user_watchlist(user.id)
            assert len(rows) == 1
            assert "already" in second.lower()
            assert "NVDA" in first

    run(scenario())


def test_remove_watchlist_item(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1011, username="tester", full_name="Test User")
            repo = WatchlistRepository(session)
            await repo.add_ticker(user.id, "TSLA", "Tesla")
            service = WatchlistService(session)
            monkeypatch.setattr(
                service,
                "extract",
                AsyncMock(return_value=WatchlistExtraction(action="remove", companies=["Tesla"], tickers=[])),
            )
            monkeypatch.setattr(
                "app.services.watchlist_service.company_resolver.resolve",
                lambda company: CompanyResolution(company_name=company, ticker="TSLA"),
            )
            response, _ = await service.handle(user.id, "Remove Tesla.")
            rows = await repo.get_user_watchlist(user.id)
            assert "removed" in response.lower()
            assert len(rows) == 0

    run(scenario())


def test_list_watchlist(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1012, username="tester", full_name="Test User")
            repo = WatchlistRepository(session)
            await repo.add_ticker(user.id, "AAPL", "Apple")
            await repo.add_ticker(user.id, "MSFT", "Microsoft")
            service = WatchlistService(session)
            monkeypatch.setattr(
                service,
                "extract",
                AsyncMock(return_value=WatchlistExtraction(action="list", companies=[], tickers=[])),
            )
            response, _ = await service.handle(user.id, "What am I watching?")
            assert "AAPL" in response
            assert "MSFT" in response

    run(scenario())


def test_natural_language_watchlist_requests(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(1013, username="tester", full_name="Test User")
            service = WatchlistService(session)
            monkeypatch.setattr(
                service,
                "extract",
                AsyncMock(return_value=WatchlistExtraction(action="add", companies=["Apple", "Microsoft"], tickers=[])),
            )
            monkeypatch.setattr(
                "app.services.watchlist_service.company_resolver.resolve",
                lambda company: CompanyResolution(company_name=company, ticker={"Apple": "AAPL", "Microsoft": "MSFT"}[company]),
            )
            response, _ = await service.handle(user.id, "Track Apple and Microsoft.")
            rows = await WatchlistRepository(session).get_user_watchlist(user.id)
            tickers = sorted([row.ticker for row in rows])
            assert tickers == ["AAPL", "MSFT"]
            assert "watchlist" in response.lower()

    run(scenario())
