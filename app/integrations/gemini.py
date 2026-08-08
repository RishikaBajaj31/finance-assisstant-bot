"""Gemini API client wrapper for LLM generation and embeddings generation."""

import json
from typing import Any, Dict, List, Optional
from google import genai
from google.genai import types
from app.config import settings
from app.core.logging import logger


class GeminiClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.client = None

        if self.api_key and self.api_key != "mock-key":
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")

    async def generate_response(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate text response using Gemini 2.5 Flash model."""
        if not self.client:
            logger.info("Gemini API client running in offline mode. Returning fallback model output.")
            return self._mock_response(prompt)

        try:
            config = {}
            if system_instruction:
                config["system_instruction"] = system_instruction

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config if config else None,
            )
            return response.text if response.text else "No response generated."
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}")
            return self._mock_response(prompt)

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        default: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a JSON object from Gemini or return a safe default."""
        if not self.client:
            return default or {}

        try:
            config = {
                "response_mime_type": "application/json",
                "temperature": 0,
            }
            if system_instruction:
                config["system_instruction"] = system_instruction

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(**config),
            )
            return self._parse_json_object(response.text or "", default=default or {})
        except Exception as e:
            logger.error(f"Error calling Gemini JSON API: {e}")
            return default or {}

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate text embedding vector using text-embedding-004."""
        if not self.client:
            # Deterministic mock vector of dimension 768
            return [0.01 * (i % 10) for i in range(768)]

        try:
            config = types.EmbedContentConfig(output_dimensionality=768)
            res = self.client.models.embed_content(
                model=self.embedding_model,
                contents=text,
                config=config,
            )
            if hasattr(res, "embedding") and getattr(res.embedding, "values", None):
                values = list(res.embedding.values)
            elif hasattr(res, "embeddings") and res.embeddings:
                first = res.embeddings[0]
                if getattr(first, "values", None):
                    values = list(first.values)
                else:
                    raise AttributeError("EmbedContentResponse did not include embedding values")
            else:
                raise AttributeError("EmbedContentResponse did not include embedding values")

            if len(values) > 768:
                return values[:768]
            if len(values) < 768:
                return values + [0.0] * (768 - len(values))
            return values
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return [0.01 * (i % 10) for i in range(768)]

    def _parse_json_object(self, text: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        default = default or {}
        raw = text.strip()
        if not raw:
            return default

        candidates = [raw]
        if "{" in raw and "}" in raw:
            candidates.append(raw[raw.find("{") : raw.rfind("}") + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
        return default

    def _mock_response(self, prompt: str) -> str:
        """Fallback mock response generator when Gemini key is not configured."""
        p_lower = prompt.lower()
        if "research" in p_lower or "compare" in p_lower or "nvda" in p_lower or "amd" in p_lower:
            return (
                "**Business Overview**\n"
                "• **Nvidia (NVDA)** dominates AI training hardware with >80% market share.\n"
                "• **AMD** is the primary challenger with MI300 series accelerators.\n\n"
                "**Financial Health & Growth**\n"
                "• NVDA: Exponential revenue growth (+120% YoY driven by Data Center).\n"
                "• AMD: Steady growth in server CPUs, scaling AI GPU production.\n\n"
                "**Risks & Outlook**\n"
                "• High valuation multiples for NVDA; supply chain bottlenecks at TSMC.\n"
                "• **Verdict**: NVDA leads leadership tier; AMD represents high-upside challenger."
            )
        return "I have updated your financial preferences and saved them to memory. How else can I assist your portfolio today?"


gemini_client = GeminiClient()
