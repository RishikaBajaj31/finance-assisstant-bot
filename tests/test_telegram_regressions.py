import asyncio

from unittest.mock import AsyncMock

from app.agents.nodes.router_node import router_node
from app.database.connection import AsyncSessionLocal, Base, engine
from app.database.migrations.ensure_schema import ensure_schema
from app.database.repositories.user_repo import UserRepository
from app.integrations.gemini import gemini_client
from app.services.company_resolution import CompanyResolution
from app.services.onboarding_service import OnboardingService
from app.services.user_service import UserService
from app.telegram.bot import telegram_bot
from app.telegram.handlers import process_update


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


async def create_user(telegram_id: int):
    async with AsyncSessionLocal() as session:
        return await UserService(session).get_or_create_user(telegram_id, username="tester", full_name="Test User")


def test_fresher_is_recognized_as_role(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            service = OnboardingService(session)
            monkeypatch.setattr(gemini_client, "generate_json", AsyncMock(return_value={}))
            extracted = await service.extract("I am a fresher", {})
            assert extracted.role == "fresher"

    run(scenario())


def test_onboarding_advances_after_fresher(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(7001, username="tester", full_name="Test User")
            service = OnboardingService(session)
            monkeypatch.setattr(gemini_client, "generate_json", AsyncMock(return_value={}))
            monkeypatch.setattr(
                "app.services.onboarding_service.company_resolver.resolve_many",
                lambda refs: [CompanyResolution(company_name="Nvidia", ticker="NVDA")] if refs else [],
            )

            response = await service.handle(user, "I am a fresher")
            refreshed = await UserRepository(session).get_by_id(user.id)

            assert refreshed.role == "fresher"
            assert "Which companies or sectors do you follow most closely?" in response

    run(scenario())


def test_onboarding_completes_through_natural_conversation(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(7006, username="tester", full_name="Test User")
            service = OnboardingService(session)
            monkeypatch.setattr(gemini_client, "generate_json", AsyncMock(return_value={}))
            monkeypatch.setattr(
                "app.services.onboarding_service.company_resolver.resolve_many",
                lambda refs: [CompanyResolution(company_name="Nvidia", ticker="NVDA")] if refs else [],
            )

            first = await service.handle(user, "I am a fresher")
            refreshed = await UserRepository(session).get_by_id(user.id)
            second = await service.handle(refreshed, "I follow Nvidia and AI companies.")
            refreshed = await UserRepository(session).get_by_id(user.id)
            third = await service.handle(refreshed, "9 AM")
            refreshed = await UserRepository(session).get_by_id(user.id)
            fourth = await service.handle(refreshed, "India")
            final_user = await UserRepository(session).get_by_id(user.id)

            assert "Which companies or sectors do you follow most closely?" in first
            assert "What time would you like your daily briefing?" in second
            assert "Which timezone should I use" in third
            assert "keep learning" in fourth.lower()
            assert final_user.onboarding_complete is True

    run(scenario())


def test_completed_onboarding_routes_news_instead_of_onboarding(monkeypatch):
    async def scenario():
        await reset_db()
        async with AsyncSessionLocal() as session:
            user = await UserService(session).get_or_create_user(7002, username="tester", full_name="Test User")
            await UserRepository(session).update_user_profile(
                user.id,
                role="fresher",
                briefing_time="09:00",
                timezone="Asia/Kolkata",
                onboarding_complete=True,
            )
            await session.commit()

            monkeypatch.setattr(gemini_client, "generate_response", AsyncMock(return_value="news"))
            state = {
                "telegram_id": 7002,
                "user_id": str(user.id),
                "user_name": "Test User",
                "input_text": "What is the latest news on Nvidia?",
                "intent": "general",
                "is_onboarded": True,
                "conversation_history": "",
                "recalled_memories": [],
                "document_id": None,
                "response": "",
                "metadata": {"user": user},
                "db_session": session,
            }
            routed = await router_node(state)
            assert routed["intent"] == "news"

    run(scenario())


def test_duplicate_telegram_update_id_is_processed_once(monkeypatch):
    async def scenario():
        await reset_db()
        sent_messages = []

        async def fake_send_message(chat_id, text):
            sent_messages.append(text)
            return True

        monkeypatch.setattr(telegram_bot, "send_message", fake_send_message)
        monkeypatch.setattr(
            "app.telegram.handlers.run_agent",
            AsyncMock(return_value={"response": "Hello from the assistant", "conversation_history": "", "recalled_memories": []}),
        )
        monkeypatch.setattr(gemini_client, "generate_json", AsyncMock(return_value={}))

        payload = {
            "update_id": 9001,
            "message": {
                "message_id": 11,
                "date": 1754670000,
                "chat": {"id": 7004, "type": "private"},
                "from": {"id": 7004, "is_bot": False, "first_name": "Test", "username": "tester"},
                "text": "Hello there",
            },
        }

        async with AsyncSessionLocal() as session:
            await create_user(7004)
            first = await process_update(payload, session)
            second = await process_update(payload, session)

            assert first["telegram_sent"] is True
            assert second["skipped"] is True
            assert len(sent_messages) == 1

    run(scenario())


def test_same_text_with_different_update_ids_are_both_processed(monkeypatch):
    async def scenario():
        await reset_db()
        sent_messages = []

        async def fake_send_message(chat_id, text):
            sent_messages.append(text)
            return True

        monkeypatch.setattr(telegram_bot, "send_message", fake_send_message)
        monkeypatch.setattr(
            "app.telegram.handlers.run_agent",
            AsyncMock(return_value={"response": "Hello from the assistant", "conversation_history": "", "recalled_memories": []}),
        )
        monkeypatch.setattr(gemini_client, "generate_json", AsyncMock(return_value={}))

        payload_1 = {
            "update_id": 9002,
            "message": {
                "message_id": 12,
                "date": 1754670000,
                "chat": {"id": 7005, "type": "private"},
                "from": {"id": 7005, "is_bot": False, "first_name": "Test", "username": "tester"},
                "text": "Hello there",
            },
        }
        payload_2 = {
            "update_id": 9003,
            "message": {
                "message_id": 13,
                "date": 1754670001,
                "chat": {"id": 7005, "type": "private"},
                "from": {"id": 7005, "is_bot": False, "first_name": "Test", "username": "tester"},
                "text": "Hello there",
            },
        }

        async with AsyncSessionLocal() as session:
            await create_user(7005)
            first = await process_update(payload_1, session)
            second = await process_update(payload_2, session)

            assert first["telegram_sent"] is True
            assert second["telegram_sent"] is True
            assert len(sent_messages) == 2

    run(scenario())
