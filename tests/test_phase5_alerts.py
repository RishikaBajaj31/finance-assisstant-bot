import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from app.agents.nodes.router_node import router_node
from app.agents.state import AgentState
from app.database.connection import AsyncSessionLocal, Base, engine
from app.database.migrations.ensure_schema import ensure_schema
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.watchlist_repo import AlertRepository, WatchlistRepository
from app.integrations.gemini import gemini_client
from app.integrations.yfinance_client import yfinance_client
from app.services.alert_service import AlertExtraction, AlertService
from app.services.company_resolution import CompanyResolution
from app.services.user_service import UserService
from app.scheduler.alert_job import run_alert_checks
from app.telegram.bot import telegram_bot


TABLES = [
    "document_chunks",
    "documents",
    "research_history",
    "alerts",
    "watchlists",
    "telegram_updates",
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


async def create_user(telegram_id: int, timezone_name: str = "UTC"):
    async with AsyncSessionLocal() as session:
        user = await UserService(session).get_or_create_user(telegram_id, username="tester", full_name="Test User")
        await UserRepository(session).update_user_profile(user.id, timezone=timezone_name)
        await session.commit()
        return await UserRepository(session).get_by_id(user.id)


def _make_state(user, text: str) -> AgentState:
    return {
        "telegram_id": user.telegram_id,
        "user_id": str(user.id),
        "user_name": user.full_name,
        "input_text": text,
        "intent": "general",
        "is_onboarded": True,
        "conversation_history": "",
        "recalled_memories": [],
        "document_id": None,
        "response": "",
        "metadata": {"chat_id": user.telegram_id, "user": user},
        "db_session": None,
    }


def test_router_routes_alert_intent():
    async def scenario():
        await reset_db()
        user = await create_user(4001)
        async with AsyncSessionLocal() as session:
            state = _make_state(user, "Alert me if Nvidia falls below $150.")
            state["db_session"] = session
            routed = await router_node(state)
            assert routed["intent"] == "alert"

    run(scenario())


def test_natural_language_price_alert_creation(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4002)
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            monkeypatch.setattr(
                "app.services.alert_service.company_resolver.resolve",
                lambda ref: CompanyResolution(company_name="Nvidia", ticker="NVDA"),
            )
            response = await service.handle(user, "Alert me if Nvidia falls below $150.")
            alerts = await AlertRepository(session).get_user_active_alerts(user.id)
            assert "falls below $150.00" in response
            assert len(alerts) == 1
            assert alerts[0].alert_type == "price_threshold"
            assert alerts[0].ticker == "NVDA"
            assert alerts[0].threshold == 150.0

    run(scenario())


def test_natural_language_percentage_alert_creation(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4003)
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            monkeypatch.setattr(
                "app.services.alert_service.company_resolver.resolve",
                lambda ref: CompanyResolution(company_name="Tesla", ticker="TSLA"),
            )
            response = await service.handle(user, "Notify me if Tesla moves more than 5% today.")
            alerts = await AlertRepository(session).get_user_active_alerts(user.id)
            assert "moves more than 5%" in response.lower()
            assert len(alerts) == 1
            assert alerts[0].alert_type == "percent_move"
            assert alerts[0].ticker == "TSLA"

    run(scenario())


def test_earnings_alert_creation(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4004)
        earnings_dt = datetime.now(timezone.utc) + timedelta(days=7)
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            monkeypatch.setattr(
                "app.services.alert_service.company_resolver.resolve",
                lambda ref: CompanyResolution(company_name="Apple", ticker="AAPL"),
            )
            monkeypatch.setattr("app.services.alert_service.yfinance_client.get_next_earnings_datetime", lambda symbol: earnings_dt)
            response = await service.handle(user, "Remind me one hour before Apple's next earnings call.")
            alerts = await AlertRepository(session).get_user_active_alerts(user.id)
            assert "remind you before" in response.lower()
            assert len(alerts) == 1
            assert alerts[0].alert_type == "earnings"
            assert alerts[0].reminder_minutes == 60
            assert alerts[0].reminder_at_utc is not None

    run(scenario())


def test_news_alert_creation(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4005)
        async with AsyncSessionLocal() as session:
            await WatchlistRepository(session).add_ticker(user.id, "NVDA", "Nvidia")
            service = AlertService(session)
            response = await service.handle(user, "Alert me if anything major happens with the companies I'm watching.")
            alerts = await AlertRepository(session).get_user_active_alerts(user.id)
            assert "watch" in response.lower()
            assert len(alerts) == 1
            assert alerts[0].alert_type == "major_news"
            assert alerts[0].scope == "watchlist"

    run(scenario())


def test_invalid_ticker_rejected(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4006)
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            monkeypatch.setattr("app.services.alert_service.company_resolver.resolve", lambda ref: None)
            response = await service.handle(user, "Alert me if XQZ falls below $10.")
            alerts = await AlertRepository(session).get_user_active_alerts(user.id)
            assert "which company do you mean" in response.lower()
            assert len(alerts) == 0

    run(scenario())


def test_ambiguous_company_rejected(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4007)
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            monkeypatch.setattr("app.services.alert_service.company_resolver.resolve", lambda ref: None)
            response = await service.handle(user, "Alert me if Apple or Tesla moves.")
            alerts = await AlertRepository(session).get_user_active_alerts(user.id)
            assert "which company do you mean" in response.lower()
            assert len(alerts) == 0

    run(scenario())


def test_alert_persistence_and_listing(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4008)
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            monkeypatch.setattr(
                "app.services.alert_service.company_resolver.resolve",
                lambda ref: CompanyResolution(company_name="Nvidia", ticker="NVDA"),
            )
            await service.handle(user, "Alert me if Nvidia falls below $150.")
            await service.handle(user, "Notify me if Nvidia moves more than 5% today.")
            listing = await service.list_alerts(user.id)
            alerts = await AlertRepository(session).get_user_active_alerts(user.id)
            assert "Here are your active alerts" in listing
            assert "price_threshold" not in listing.lower()
            assert len(alerts) == 2

    run(scenario())


def test_alert_cancellation(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4009)
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            monkeypatch.setattr(
                "app.services.alert_service.company_resolver.resolve",
                lambda ref: CompanyResolution(company_name="Nvidia", ticker="NVDA"),
            )
            await service.handle(user, "Alert me if Nvidia falls below $150.")
            response = await service.handle(user, "Cancel my Nvidia alert.")
            alerts = await AlertRepository(session).get_user_alerts(user.id)
            assert "cancelled" in response.lower()
            assert all(not alert.is_active for alert in alerts)

    run(scenario())


def test_price_condition_triggering(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4010)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user.id,
                ticker="NVDA",
                alert_type="price_threshold",
                condition="price_below",
                threshold=150.0,
                title="Nvidia",
            )
            await session.commit()
            monkeypatch.setattr(
                "app.services.alert_service.yfinance_client.get_ticker_info",
                lambda symbol: {"symbol": symbol, "name": "Nvidia", "current_price": 148.72},
            )
            service = AlertService(session)
            triggered = await service.evaluate_active_alerts()
            alerts = await repo.get_user_alerts(user.id)
            assert len(triggered) == 1
            assert "148.72" in triggered[0]["message"]
            assert alerts[0].triggered is True
            assert alerts[0].is_active is False

    run(scenario())


def test_percentage_condition_triggering(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4011)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user.id,
                ticker="TSLA",
                alert_type="percent_move",
                condition="percent_move_gt",
                threshold=5.0,
                title="Tesla",
            )
            await session.commit()
            monkeypatch.setattr("app.services.alert_service.yfinance_client.get_daily_move_pct", lambda symbol: 5.8)
            monkeypatch.setattr(
                "app.services.alert_service.yfinance_client.get_ticker_info",
                lambda symbol: {"symbol": symbol, "name": "Tesla", "current_price": 202.11},
            )
            triggered = await AlertService(session).evaluate_active_alerts()
            assert len(triggered) == 1
            assert "5.8" in triggered[0]["message"]

    run(scenario())


def test_earnings_reminder_triggering(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4012)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user.id,
                ticker="AAPL",
                alert_type="earnings",
                condition="earnings_reminder",
                reminder_minutes=60,
                reminder_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
                event_at_utc=datetime.now(timezone.utc) + timedelta(days=7),
                title="Apple",
            )
            await session.commit()
            monkeypatch.setattr(
                "app.services.alert_service.yfinance_client.get_ticker_info",
                lambda symbol: {"symbol": symbol, "name": "Apple", "current_price": 200.0},
            )
            triggered = await AlertService(session).evaluate_active_alerts()
            assert len(triggered) == 1
            assert "Reminder" in triggered[0]["message"] or "reminder" in triggered[0]["message"].lower()

    run(scenario())


def test_duplicate_trigger_prevention(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4013)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user.id,
                ticker="NVDA",
                alert_type="price_threshold",
                condition="price_below",
                threshold=150.0,
                title="Nvidia",
            )
            await session.commit()
            monkeypatch.setattr(
                "app.services.alert_service.yfinance_client.get_ticker_info",
                lambda symbol: {"symbol": symbol, "name": "Nvidia", "current_price": 149.0},
            )
            service = AlertService(session)
            first = await service.evaluate_active_alerts()
            second = await service.evaluate_active_alerts()
            assert len(first) == 1
            assert len(second) == 0

    run(scenario())


def test_telegram_notification(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4014)
        sent = []

        async def fake_send_message(chat_id, text):
            sent.append((chat_id, text))
            return True

        monkeypatch.setattr(telegram_bot, "send_message", fake_send_message)
        monkeypatch.setattr(
            "app.services.alert_service.yfinance_client.get_ticker_info",
            lambda symbol: {"symbol": symbol, "name": "Nvidia", "current_price": 149.0},
        )
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user.id,
                ticker="NVDA",
                alert_type="price_threshold",
                condition="price_below",
                threshold=150.0,
                title="Nvidia",
            )
            await session.commit()
        triggered = await run_alert_checks()
        assert len(triggered) == 1
        assert sent and sent[0][0] == user.telegram_id

    run(scenario())


def test_user_isolation(monkeypatch):
    async def scenario():
        await reset_db()
        user_a = await create_user(4015)
        user_b = await create_user(4016)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user_a.id,
                ticker="NVDA",
                alert_type="price_threshold",
                condition="price_below",
                threshold=150.0,
                title="Nvidia",
            )
            await session.commit()
            monkeypatch.setattr(
                "app.services.alert_service.yfinance_client.get_ticker_info",
                lambda symbol: {"symbol": symbol, "name": "Nvidia", "current_price": 149.0},
            )
            triggered = await AlertService(session).evaluate_active_alerts()
            assert len(triggered) == 1
            assert triggered[0]["user_id"] == str(user_a.id)
            assert triggered[0]["chat_id"] == user_a.telegram_id
            assert await AlertRepository(session).get_user_active_alerts(user_b.id) == []

    run(scenario())


def test_timezone_handling(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4017, timezone_name="Asia/Kolkata")
        async with AsyncSessionLocal() as session:
            service = AlertService(session)
            captured = {}

            async def fake_extract(text, user_context=None):
                captured["user_context"] = user_context
                return AlertExtraction(
                    action="list",
                    alert_type=None,
                    companies=[],
                    tickers=[],
                    condition=None,
                    threshold=None,
                    reminder_minutes=None,
                    scope=None,
                    target=None,
                    skip=False,
                )

            monkeypatch.setattr(service, "extract", fake_extract)
            await service.handle(user, "What alerts do I have?")
            assert captured["user_context"]["timezone"] == "Asia/Kolkata"

    run(scenario())


def test_scheduler_failure_isolation(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4018)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user.id,
                ticker="NVDA",
                alert_type="price_threshold",
                condition="price_below",
                threshold=150.0,
                title="Nvidia",
            )
            await repo.create_alert(
                user_id=user.id,
                ticker="TSLA",
                alert_type="price_threshold",
                condition="price_below",
                threshold=300.0,
                title="Tesla",
            )
            await session.commit()

            def fake_ticker_info(symbol):
                if symbol == "NVDA":
                    raise RuntimeError("market api failed")
                return {"symbol": symbol, "name": "Tesla", "current_price": 299.0}

            monkeypatch.setattr("app.services.alert_service.yfinance_client.get_ticker_info", fake_ticker_info)
            triggered = await AlertService(session).evaluate_active_alerts()
            assert len(triggered) == 1
            assert triggered[0]["ticker"] == "TSLA"

    run(scenario())


def test_api_failure_handling(monkeypatch):
    async def scenario():
        await reset_db()
        user = await create_user(4019)
        async with AsyncSessionLocal() as session:
            repo = AlertRepository(session)
            await repo.create_alert(
                user_id=user.id,
                ticker="NVDA",
                alert_type="major_news",
                condition="major_news",
                title="Nvidia",
            )
            await session.commit()
            monkeypatch.setattr("app.services.alert_service.yfinance_client.get_recent_news", lambda ticker, limit=5: (_ for _ in ()).throw(RuntimeError("news api failed")))
            triggered = await AlertService(session).evaluate_active_alerts()
            assert triggered == []

    run(scenario())
