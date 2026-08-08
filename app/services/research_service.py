"""Financial research orchestration service."""

from typing import List
from app.integrations.yfinance_client import yfinance_client
from app.integrations.gemini import gemini_client
from app.core.logging import logger


class ResearchService:
    async def analyze_company_or_comparison(self, query: str, tickers: List[str]) -> str:
        """Perform deep financial analysis with fundamental data and analyst verdict."""
        if not tickers:
            tickers = ["NVDA", "AMD"] if "compare" in query.lower() else ["NVDA"]

        gathered_data = []
        for ticker in tickers[:2]:
            info = yfinance_client.get_ticker_info(ticker)
            news = yfinance_client.get_recent_news(ticker, limit=2)
            gathered_data.append({"info": info, "news": news})

        prompt = (
            f"User Query: '{query}'\n"
            f"Financial Fundamentals Data: {gathered_data}\n\n"
            "Provide a senior financial analyst research report with these EXACT sections:\n"
            "1. **Business Overview**: What each company does & market position\n"
            "2. **Financials & Valuation**: P/E, Revenue Growth, Key Metrics with WHY it matters\n"
            "3. **Growth Catalysts**: Future expansion drivers\n"
            "4. **Recent News & Catalysts**: Key events & strategic impact\n"
            "5. **Key Investment Risks**: Supply chain, macroeconomic, valuation risks\n"
            "6. **Investment Summary**: Clear action-oriented verdict with reasoning\n\n"
            "Keep it concise, analyst-grade, and beautifully structured with bullet points."
        )

        system_instruction = (
            "You are a Senior Staff Financial Analyst at a top investment firm. "
            "Never give generic AI disclaimers. Provide sharp, insightful financial intelligence."
        )

        return await gemini_client.generate_response(prompt, system_instruction=system_instruction)


research_service = ResearchService()
