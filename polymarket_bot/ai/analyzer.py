import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

import aiohttp

from ..client import MarketInfo
from ..utils.logging import get_logger

log = get_logger(__name__)

@dataclass
class AIAnalysis:
    market_id: str
    prediction: float
    confidence: float
    reasoning: str
    risk_factors: list[str]
    catalysts: list[str]
    recommendation: str
    timestamp: datetime

class AIProvider(ABC):
    @abstractmethod
    async def analyze(self, prompt: str) -> str:
        pass

class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str = None, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = "https://api.openai.com/v1/chat/completions"

    async def analyze(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")

        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert prediction market analyst. Analyze markets objectively and provide probabilistic assessments."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 1000
            }

            async with session.post(self.base_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    log.error("openai_error", status=resp.status, error=error)
                    raise Exception(f"OpenAI API error: {resp.status}")
                
                data = await resp.json()
                return data["choices"][0]["message"]["content"]

class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str = None, model: str = "claude-3-opus-20240229"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def analyze(self, prompt: str) -> str:
        if not self.api_key:
            raise ValueError("Anthropic API key not configured")

        async with aiohttp.ClientSession() as session:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "max_tokens": 1000,
                "system": "You are an expert prediction market analyst. Analyze markets objectively and provide probabilistic assessments.",
                "messages": [{"role": "user", "content": prompt}]
            }

            async with session.post(self.base_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    log.error("anthropic_error", status=resp.status, error=error)
                    raise Exception(f"Anthropic API error: {resp.status}")
                
                data = await resp.json()
                return data["content"][0]["text"]

class MarketAIAnalyzer:
    def __init__(self, provider: str = "openai"):
        self.provider = self._get_provider(provider)
        self._cache: dict[str, AIAnalysis] = {}
        self._cache_ttl = 3600

    def _get_provider(self, name: str) -> AIProvider:
        providers = {
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
            "claude": AnthropicProvider,
        }
        provider_class = providers.get(name.lower(), OpenAIProvider)
        return provider_class()

    async def analyze_market(
        self,
        market: MarketInfo,
        price_history: list[dict] = None,
        news_context: str = None
    ) -> AIAnalysis:
        cache_key = f"{market.condition_id}_{datetime.now(UTC).strftime('%Y%m%d%H')}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        prompt = self._build_analysis_prompt(market, price_history, news_context)
        
        try:
            response = await self.provider.analyze(prompt)
            analysis = self._parse_response(market.condition_id, response)
            self._cache[cache_key] = analysis
            return analysis
        except Exception as e:
            log.error("ai_analysis_error", market=market.condition_id, error=str(e))
            return self._fallback_analysis(market)

    def _build_analysis_prompt(
        self,
        market: MarketInfo,
        price_history: list[dict] = None,
        news_context: str = None
    ) -> str:
        prompt = f"""Analyze this prediction market:

**Question:** {market.question}

**Current Prices:**
- YES: {market.yes_token.price:.2%}
- NO: {market.no_token.price:.2%}

**Market Data:**
- 24h Volume: ${market.volume_24h:,.0f}
- Liquidity: ${market.liquidity:,.0f}
- Category: {market.category}
"""

        if market.end_date:
            days_left = market.days_to_resolution
            prompt += f"- Resolution in: {days_left:.1f} days\n"

        if price_history:
            recent_prices = price_history[-10:]
            prompt += "\n**Recent Price History (YES):**\n"
            for p in recent_prices:
                prompt += f"- {p.get('timestamp', 'N/A')}: {p.get('price', 0):.2%}\n"

        if news_context:
            prompt += f"\n**Relevant News/Context:**\n{news_context}\n"

        prompt += """
**Please analyze and provide:**
1. Your probability estimate (0-100%)
2. Confidence level in your estimate (LOW/MEDIUM/HIGH)
3. Key reasoning (2-3 sentences)
4. Main risk factors (bullet points)
5. Potential catalysts that could move the market
6. Trading recommendation (BUY YES / BUY NO / HOLD / AVOID)

Format your response as JSON:
{
    "probability": 65,
    "confidence": "MEDIUM",
    "reasoning": "...",
    "risk_factors": ["...", "..."],
    "catalysts": ["...", "..."],
    "recommendation": "HOLD"
}
"""
        return prompt

    def _parse_response(self, market_id: str, response: str) -> AIAnalysis:
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

            confidence_map = {"LOW": 0.3, "MEDIUM": 0.6, "HIGH": 0.85}

            return AIAnalysis(
                market_id=market_id,
                prediction=data.get("probability", 50) / 100,
                confidence=confidence_map.get(data.get("confidence", "MEDIUM").upper(), 0.5),
                reasoning=data.get("reasoning", ""),
                risk_factors=data.get("risk_factors", []),
                catalysts=data.get("catalysts", []),
                recommendation=data.get("recommendation", "HOLD"),
                timestamp=datetime.now(UTC)
            )
        except Exception as e:
            log.warning("ai_parse_error", error=str(e), response=response[:200])
            return AIAnalysis(
                market_id=market_id,
                prediction=0.5,
                confidence=0.3,
                reasoning=response[:500] if response else "Analysis failed",
                risk_factors=["Unable to parse structured response"],
                catalysts=[],
                recommendation="HOLD",
                timestamp=datetime.now(UTC)
            )

    def _fallback_analysis(self, market: MarketInfo) -> AIAnalysis:
        return AIAnalysis(
            market_id=market.condition_id,
            prediction=market.yes_token.price,
            confidence=0.3,
            reasoning="AI analysis unavailable, using market price as estimate",
            risk_factors=["AI service unavailable"],
            catalysts=[],
            recommendation="HOLD",
            timestamp=datetime.now(UTC)
        )

    async def batch_analyze(
        self,
        markets: list[MarketInfo],
        max_concurrent: int = 3
    ) -> list[AIAnalysis]:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(market):
            async with semaphore:
                return await self.analyze_market(market)

        tasks = [analyze_with_semaphore(m) for m in markets]
        return await asyncio.gather(*tasks)

    async def get_risk_assessment(
        self,
        markets: list[MarketInfo],
        total_exposure: float
    ) -> dict:
        prompt = f"""Analyze the risk of this prediction market portfolio:

**Total Exposure:** ${total_exposure:,.2f}

**Positions:**
"""
        for market in markets[:10]:
            prompt += f"- {market.question[:60]}: YES @ {market.yes_token.price:.0%}\n"

        prompt += """
Provide a risk assessment with:
1. Overall risk level (1-10)
2. Correlation concerns
3. Event clustering risk
4. Recommendations to reduce risk

Format as JSON:
{
    "risk_level": 5,
    "correlation_concerns": "...",
    "event_clustering": "...",
    "recommendations": ["...", "..."]
}
"""
        try:
            response = await self.provider.analyze(prompt)
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            if json_start != -1:
                return json.loads(response[json_start:json_end])
        except Exception as e:
            log.error("risk_assessment_error", error=str(e))

        return {
            "risk_level": 5,
            "correlation_concerns": "Unable to assess",
            "event_clustering": "Unable to assess",
            "recommendations": ["Diversify across uncorrelated events"]
        }

ai_analyzer = MarketAIAnalyzer()
