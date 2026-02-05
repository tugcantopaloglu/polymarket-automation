import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from polymarket_bot.ai.analyzer import (
    AIAnalysis,
    MarketAIAnalyzer,
    OpenAIProvider,
    AnthropicProvider,
)
from polymarket_bot.client import MarketInfo, TokenInfo


@pytest.fixture
def sample_market():
    return MarketInfo(
        condition_id="test-market-123",
        question="Will BTC exceed $100,000 by end of 2024?",
        yes_token=TokenInfo(
            token_id="yes-token",
            outcome="Yes",
            price=0.45,
            volume_24h=50000,
            price_change_24h=0.05
        ),
        no_token=TokenInfo(
            token_id="no-token",
            outcome="No",
            price=0.54,
            volume_24h=45000,
            price_change_24h=-0.05
        ),
        volume_24h=95000,
        liquidity=25000,
        end_date=datetime.now(UTC) + timedelta(days=30),
        category="Crypto"
    )


class TestAIAnalysis:
    def test_analysis_creation(self):
        analysis = AIAnalysis(
            market_id="test-123",
            prediction=0.65,
            confidence=0.8,
            reasoning="Strong fundamentals",
            risk_factors=["Market volatility"],
            catalysts=["ETF approval"],
            recommendation="BUY YES",
            timestamp=datetime.now(UTC)
        )
        
        assert analysis.prediction == 0.65
        assert analysis.confidence == 0.8
        assert len(analysis.risk_factors) == 1


class TestOpenAIProvider:
    @pytest.fixture
    def provider(self):
        return OpenAIProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_analyze_success(self, provider):
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"probability": 65, "confidence": "HIGH", "reasoning": "Test", "risk_factors": [], "catalysts": [], "recommendation": "HOLD"}'
                }
            }]
        }
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)
            
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_resp
            mock_ctx.__aexit__.return_value = None
            
            mock_session_instance = AsyncMock()
            mock_session_instance.post.return_value = mock_ctx
            mock_session_instance.__aenter__.return_value = mock_session_instance
            mock_session_instance.__aexit__.return_value = None
            mock_session.return_value = mock_session_instance
            
            result = await provider.analyze("Test prompt")
            assert "probability" in result

    @pytest.mark.asyncio
    async def test_analyze_no_api_key(self):
        provider = OpenAIProvider(api_key=None)
        with patch.dict('os.environ', {}, clear=True):
            provider.api_key = None
            with pytest.raises(ValueError, match="API key"):
                await provider.analyze("Test")


class TestAnthropicProvider:
    @pytest.fixture
    def provider(self):
        return AnthropicProvider(api_key="test-key")

    @pytest.mark.asyncio
    async def test_analyze_no_api_key(self):
        provider = AnthropicProvider(api_key=None)
        with patch.dict('os.environ', {}, clear=True):
            provider.api_key = None
            with pytest.raises(ValueError, match="API key"):
                await provider.analyze("Test")


class TestMarketAIAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return MarketAIAnalyzer(provider="openai")

    def test_get_provider_openai(self, analyzer):
        provider = analyzer._get_provider("openai")
        assert isinstance(provider, OpenAIProvider)

    def test_get_provider_anthropic(self, analyzer):
        provider = analyzer._get_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)

    def test_get_provider_claude_alias(self, analyzer):
        provider = analyzer._get_provider("claude")
        assert isinstance(provider, AnthropicProvider)

    def test_build_analysis_prompt(self, analyzer, sample_market):
        prompt = analyzer._build_analysis_prompt(sample_market)
        
        assert sample_market.question in prompt
        assert "YES" in prompt
        assert "NO" in prompt
        assert "probability" in prompt.lower()

    def test_build_analysis_prompt_with_history(self, analyzer, sample_market):
        history = [
            {"timestamp": "2024-01-15T10:00:00", "price": 0.42},
            {"timestamp": "2024-01-15T11:00:00", "price": 0.44}
        ]
        prompt = analyzer._build_analysis_prompt(sample_market, price_history=history)
        
        assert "Price History" in prompt

    def test_build_analysis_prompt_with_news(self, analyzer, sample_market):
        news = "Bitcoin ETF approved by SEC"
        prompt = analyzer._build_analysis_prompt(sample_market, news_context=news)
        
        assert news in prompt

    def test_parse_response_valid_json(self, analyzer):
        response = '''Here's my analysis:
        {
            "probability": 65,
            "confidence": "HIGH",
            "reasoning": "Strong market momentum",
            "risk_factors": ["Regulatory risk", "Market volatility"],
            "catalysts": ["ETF approval", "Halving event"],
            "recommendation": "BUY YES"
        }
        Some additional text.'''
        
        analysis = analyzer._parse_response("test-market", response)
        
        assert analysis.prediction == 0.65
        assert analysis.confidence == 0.85
        assert "Strong market momentum" in analysis.reasoning
        assert len(analysis.risk_factors) == 2
        assert analysis.recommendation == "BUY YES"

    def test_parse_response_invalid_json(self, analyzer):
        response = "This is not valid JSON at all"
        
        analysis = analyzer._parse_response("test-market", response)
        
        assert analysis.prediction == 0.5
        assert analysis.confidence == 0.3
        assert analysis.recommendation == "HOLD"

    def test_fallback_analysis(self, analyzer, sample_market):
        analysis = analyzer._fallback_analysis(sample_market)
        
        assert analysis.market_id == sample_market.condition_id
        assert analysis.prediction == sample_market.yes_token.price
        assert analysis.confidence == 0.3
        assert analysis.recommendation == "HOLD"

    @pytest.mark.asyncio
    async def test_analyze_market_uses_cache(self, analyzer, sample_market):
        cached_analysis = AIAnalysis(
            market_id=sample_market.condition_id,
            prediction=0.70,
            confidence=0.8,
            reasoning="Cached result",
            risk_factors=[],
            catalysts=[],
            recommendation="BUY YES",
            timestamp=datetime.now(UTC)
        )
        
        cache_key = f"{sample_market.condition_id}_{datetime.now(UTC).strftime('%Y%m%d%H')}"
        analyzer._cache[cache_key] = cached_analysis
        
        result = await analyzer.analyze_market(sample_market)
        
        assert result.prediction == 0.70
        assert result.reasoning == "Cached result"

    @pytest.mark.asyncio
    async def test_analyze_market_error_fallback(self, analyzer, sample_market):
        analyzer.provider.analyze = AsyncMock(side_effect=Exception("API Error"))
        
        result = await analyzer.analyze_market(sample_market)
        
        assert result.prediction == sample_market.yes_token.price
        assert "unavailable" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_batch_analyze(self, analyzer, sample_market):
        analyzer.analyze_market = AsyncMock(return_value=AIAnalysis(
            market_id="test",
            prediction=0.5,
            confidence=0.5,
            reasoning="Test",
            risk_factors=[],
            catalysts=[],
            recommendation="HOLD",
            timestamp=datetime.now(UTC)
        ))
        
        markets = [sample_market, sample_market]
        results = await analyzer.batch_analyze(markets, max_concurrent=2)
        
        assert len(results) == 2
        assert analyzer.analyze_market.call_count == 2

    @pytest.mark.asyncio
    async def test_get_risk_assessment(self, analyzer, sample_market):
        analyzer.provider.analyze = AsyncMock(return_value='''
        {
            "risk_level": 5,
            "correlation_concerns": "Low correlation",
            "event_clustering": "Some clustering around crypto",
            "recommendations": ["Diversify", "Reduce exposure"]
        }
        ''')
        
        result = await analyzer.get_risk_assessment([sample_market], 1000.0)
        
        assert "risk_level" in result
        assert isinstance(result["recommendations"], list)

    @pytest.mark.asyncio
    async def test_get_risk_assessment_error(self, analyzer, sample_market):
        analyzer.provider.analyze = AsyncMock(side_effect=Exception("Error"))
        
        result = await analyzer.get_risk_assessment([sample_market], 1000.0)
        
        assert result["risk_level"] == 5
        assert "Diversify" in result["recommendations"][0]
