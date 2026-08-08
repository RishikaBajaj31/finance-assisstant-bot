"""News intelligence processing service."""

from app.integrations.news_client import news_client
from app.integrations.gemini import gemini_client


class NewsService:
    async def get_news_intelligence(self, query: str = "technology stocks") -> str:
        """Transform raw market news into structured executive intelligence."""
        raw_news = await news_client.fetch_financial_news(query=query, limit=3)

        prompt = (
            f"Raw Market News Articles: {raw_news}\n\n"
            "Analyze these headlines and format your response into 3 concise news items with EXACTLY these sub-bullets:\n"
            "• **What Happened**: (1 sentence)\n"
            "• **Why It Matters**: (1 sentence explanation of economic impact)\n"
            "• **Market Impact**: (1 sentence effect on stocks/sectors)\n"
            "• **Suggested Action**: (1 sentence actionable takeaway)\n\n"
            "Format cleanly in Markdown."
        )

        system_prompt = "You are an executive financial news intelligence strategist."
        return await gemini_client.generate_response(prompt, system_instruction=system_prompt)


news_service = NewsService()
