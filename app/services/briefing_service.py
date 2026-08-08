"""Personalized Daily Briefing generation service."""

from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories.user_repo import UserRepository
from app.database.repositories.watchlist_repo import WatchlistRepository
from app.integrations.yfinance_client import yfinance_client
from app.integrations.gemini import gemini_client


class BriefingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.watch_repo = WatchlistRepository(session)

    async def generate_user_briefing(self, telegram_id: int) -> str:
        """Construct personalized morning briefing based on user preferences & watchlist."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return "Good morning! Setup your profile to receive personalized daily briefings."

        watchlist_items = await self.watch_repo.get_user_watchlist(user.id)
        tickers = [item.ticker for item in watchlist_items] or ["NVDA", "AAPL", "MSFT"]

        quotes = {t: yfinance_client.get_ticker_info(t) for t in tickers}

        prompt = (
            f"User Profile: Role={user.role or 'Investor'}, Preferences={user.preferences}\n"
            f"Watchlist Fundamentals: {quotes}\n\n"
            "Generate a high-impact, personalized **Daily Financial Briefing** with these exact sections:\n"
            "📊 **Macro Market Snapshot**: Core indices summary & sentiment\n"
            "🎯 **Watchlist Updates**: Key movements and fundamental news for target stocks\n"
            "💡 **Economic Drivers**: Key macroeconomic catalysts today\n"
            "⚡ **Actionable Briefing Takeaway**: Concise recommendation for today's trading session.\n\n"
            "Keep it crisp, professional, formatted in Telegram Markdown."
        )

        return await gemini_client.generate_response(prompt)
