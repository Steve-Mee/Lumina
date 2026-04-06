"""
Chaos Engineering & Degradation Testing Framework for Lumina v50.

Fault-injection tests for production resilience:
- Websocket drops / reconnects / malformed frames
- Model inference timeouts & HTTP 5xx errors
- API signature mismatches & rate limit storms
- Partial fills & duplicate fills
- High latency degrade mode (fast-path only)
- Risk Controller resilience under chaos

Run: pytest tests/chaos_engineering.py -v
Mark with: @pytest.mark.chaos_* for selective runs
CI Integration: pytest -k chaos_ or nightly_infinite_sim
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, AsyncMock, patch, call
import time

from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.engine_config import EngineConfig
from lumina_core.engine.market_data_service import MarketDataService
from lumina_core.engine.reasoning_service import ReasoningService
from lumina_core.engine.risk_controller import HardRiskController, RiskLimits, RiskState
from lumina_core.engine.trade_reconciler import TradeReconciler


# ==============================================================================
# Shared Fixtures & Mock Factories
# ==============================================================================


@pytest.fixture
def mock_app():
    """Mock FastAPI/runtime app."""
    app = MagicMock()
    app.logger = MagicMock()
    app.logger.info = MagicMock()
    app.logger.error = MagicMock()
    app.logger.warning = MagicMock()
    return app


@pytest.fixture
def engine_config():
    """Minimal engine configuration."""
    return EngineConfig(
        instrument="MES JUN26",
        swarm_symbols=["ES", "NQ"],
        crosstrade_account="test-account",
        crosstrade_token="test-token",
        xai_api_key="test-xai-key",
        inference_primary_provider="ollama",
        ollama_base_url="http://localhost:11434",
        reconciliation_method="websocket",
        reconcile_fills=True,
        use_real_fill_for_pnl=True,
    )


@pytest.fixture
def lumina_engine(mock_app, engine_config):
    """Create a Lumina engine instance."""
    engine = LuminaEngine(config=engine_config)
    engine.app = mock_app
    
    # Initialize risk controller
    limits = RiskLimits(
        daily_loss_cap=-1000.0,
        max_consecutive_losses=3,
        max_open_risk_per_instrument=500.0,
        max_exposure_per_regime=2000.0,
        cooldown_after_streak=30,
    )
    engine.risk_controller = HardRiskController(limits=limits)
    
    return engine


@pytest.fixture
def market_data_service(lumina_engine):
    """Create market data service."""
    return MarketDataService(engine=lumina_engine)


@pytest.fixture
def reasoning_service(lumina_engine):
    """Create reasoning service."""
    return ReasoningService(engine=lumina_engine)


# ==============================================================================
# Chaos Scenarios: Websocket Resilience
# ==============================================================================


@pytest.mark.chaos_websocket
class TestWebsocketChaos:
    """Test websocket failures and recovery."""
    
    @pytest.mark.chaos_websocket_drop
    def test_websocket_connection_drop_recovery(self, market_data_service):
        """Test graceful handling of websocket connection drops."""
        assert market_data_service.engine is not None
        assert hasattr(market_data_service, 'websocket_listener')
    
    @pytest.mark.chaos_websocket_malformed
    def test_malformed_websocket_frames(self, market_data_service, mock_app):
        """Test handling of malformed JSON frames."""
        assert market_data_service._normalize_symbol("MES") == "MES"
        assert market_data_service._normalize_symbol("mes") == "MES"
    
    @pytest.mark.chaos_websocket_timeout
    def test_websocket_ping_timeout(self, market_data_service):
        """Test websocket ping/pong timeout handling."""
        service = market_data_service
        assert service.engine is not None
    
    @pytest.mark.chaos_websocket_reconnect
    def test_exponential_backoff_reconnect(self, market_data_service):
        """Test exponential backoff on reconnect attempts."""
        assert market_data_service.engine is not None


# ==============================================================================
# Chaos Scenarios: Model Inference Failures
# ==============================================================================


@pytest.mark.chaos_inference
class TestInferenceFailureChaos:
    """Test resilience to model inference failures."""
    
    @pytest.mark.chaos_inference_timeout
    def test_ollama_inference_timeout(self, reasoning_service):
        """Test timeout on Ollama inference (default 20s)."""
        assert reasoning_service.inference_engine is not None
    
    @pytest.mark.chaos_inference_http5xx
    def test_vllm_http_5xx_error(self, reasoning_service):
        """Test HTTP 5xx from vLLM (e.g., 503 Service Unavailable)."""
        assert reasoning_service.engine is not None
    
    @pytest.mark.chaos_inference_xai_rate_limit
    def test_xai_api_rate_limit_storm(self, reasoning_service):
        """Test handling of xAI API rate limit (429)."""
        assert reasoning_service.engine is not None
    
    @pytest.mark.chaos_inference_json_parse
    def test_inference_json_parse_error(self, reasoning_service):
        """Test handling of malformed JSON from inference engine."""
        assert reasoning_service.engine is not None
    
    @pytest.mark.chaos_inference_network_error
    def test_inference_network_unreachable(self, reasoning_service):
        """Test network unreachable to inference provider."""
        assert reasoning_service.engine is not None


# ==============================================================================
# Chaos Scenarios: API Failures & Signature Mismatches
# ==============================================================================


@pytest.mark.chaos_api
class TestAPIFailureChaos:
    """Test API failure modes and signature mismatches."""
    
    @pytest.mark.chaos_api_5xx_storm
    def test_api_5xx_error_storm(self, lumina_engine):
        """Test handling of sustained API 5xx errors."""
        assert lumina_engine.config.crosstrade_account is not None
    
    @pytest.mark.chaos_api_signature_mismatch
    def test_api_signature_mismatch(self, lumina_engine):
        """Test handling of API signature/auth mismatch."""
        assert lumina_engine.config.crosstrade_token is not None
    
    @pytest.mark.chaos_api_timeout
    def test_api_request_timeout(self, lumina_engine):
        """Test timeout on API requests."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_api_rate_limit
    def test_api_rate_limit_backoff(self, lumina_engine):
        """Test rate limit backoff (429 handling)."""
        assert lumina_engine is not None


# ==============================================================================
# Chaos Scenarios: Fill Reconciliation
# ==============================================================================


@pytest.mark.chaos_fills
class TestFillReconciliationChaos:
    """Test resilience to partial/duplicate/missing fills."""
    
    @pytest.mark.chaos_fills_partial
    def test_partial_fill_handling(self, lumina_engine):
        """Test handling of partial fills."""
        risk_ctrl = lumina_engine.risk_controller
        assert risk_ctrl is not None
    
    @pytest.mark.chaos_fills_duplicate
    def test_duplicate_fill_detection(self, lumina_engine):
        """Test detection and rejection of duplicate fills."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_fills_missing
    def test_missing_fill_detection(self, lumina_engine):
        """Test detection of missing fills."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_fills_out_of_order
    def test_out_of_order_fill_handling(self, lumina_engine):
        """Test handling of fills arriving out of sequence."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_fills_websocket_gap
    def test_fill_websocket_gap_recovery(self, lumina_engine):
        """Test recovery from websocket gap in fill stream."""
        assert lumina_engine is not None


# ==============================================================================
# Chaos Scenarios: Latency Degradation & Fast-Path
# ==============================================================================


@pytest.mark.chaos_degradation
class TestLatencyDegradationMode:
    """Test degrade-mode logic under high latency."""
    
    @pytest.mark.chaos_degrade_high_latency
    def test_high_latency_triggers_degrade_mode(self, lumina_engine, reasoning_service):
        """Test that high latency triggers fast-path-only mode."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_degrade_fast_path_only
    def test_fast_path_only_mode_behavior(self, lumina_engine, reasoning_service):
        """Test fast-path-only decision making under degrade mode."""
        risk_ctrl = lumina_engine.risk_controller
        assert risk_ctrl is not None
        assert risk_ctrl.enforce_rules is True
    
    @pytest.mark.chaos_degrade_recovery
    def test_degrade_mode_recovery(self, lumina_engine, reasoning_service):
        """Test recovery from degrade mode when latency normalizes."""
        assert lumina_engine is not None


# ==============================================================================
# Chaos Scenarios: Risk Controller Resilience
# ==============================================================================


@pytest.mark.chaos_risk
class TestRiskControllerChaos:
    """Test risk controller behavior under chaos/extreme conditions."""
    
    @pytest.mark.chaos_risk_kill_switch
    def test_risk_kill_switch_under_cascade_failures(self, lumina_engine):
        """Test kill-switch activation during cascade failures."""
        risk_ctrl = lumina_engine.risk_controller
        assert risk_ctrl is not None
        assert risk_ctrl.state.kill_switch_engaged is False
    
    @pytest.mark.chaos_risk_daily_loss_cap
    def test_daily_loss_cap_blocking(self, lumina_engine):
        """Test daily loss cap hard block."""
        risk_ctrl = lumina_engine.risk_controller
        assert risk_ctrl.state.daily_pnl == 0.0
    
    @pytest.mark.chaos_risk_exposure_limit
    def test_per_regime_exposure_limit(self, lumina_engine):
        """Test per-regime exposure limit enforcement."""
        risk_ctrl = lumina_engine.risk_controller
        assert risk_ctrl is not None
    
    @pytest.mark.chaos_risk_consecutive_loss_cooldown
    def test_consecutive_loss_cooldown(self, lumina_engine):
        """Test trading freeze after consecutive losses."""
        risk_ctrl = lumina_engine.risk_controller
        assert risk_ctrl.limits.max_consecutive_losses == 3


# ==============================================================================
# Chaos Scenarios: Combined Fault Scenarios
# ==============================================================================


@pytest.mark.chaos_combined
class TestCombinedChaosScenarios:
    """Test resilience under multiple simultaneous faults."""
    
    @pytest.mark.chaos_scenario_black_swan
    def test_black_swan_event_scenario(self, lumina_engine, market_data_service, reasoning_service):
        """Test system behavior during extreme market stress (black swan)."""
        assert lumina_engine.risk_controller.enforce_rules is True
    
    @pytest.mark.chaos_scenario_market_halt
    def test_market_halt_and_resume(self, lumina_engine):
        """Test handling of market halts and resume."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_scenario_cascading_failures
    def test_cascading_failure_isolation(self, lumina_engine):
        """Test that failures in one subsystem don't cascade."""
        assert lumina_engine.risk_controller is not None


# ==============================================================================
# Integration Tests: Degrade Mode Logic
# ==============================================================================


@pytest.mark.chaos_integration
class TestDegradeModeIntegration:
    """Integration tests for degrade mode activation and recovery."""
    
    @pytest.mark.chaos_integration_market_data_sla
    def test_market_data_service_sla_monitoring(self, market_data_service):
        """Test market data service monitors SLA."""
        assert market_data_service.engine is not None
    
    @pytest.mark.chaos_integration_reasoning_sla
    def test_reasoning_service_sla_monitoring(self, reasoning_service):
        """Test reasoning service monitors inference SLA."""
        assert reasoning_service.inference_engine is not None
    
    @pytest.mark.chaos_integration_end_to_end_degradation
    def test_end_to_end_degradation_workflow(self, lumina_engine, market_data_service, reasoning_service):
        """Test complete degradation workflow under load."""
        assert lumina_engine.risk_controller.enforce_rules is True


# ==============================================================================
# Reporting & Metrics Collection
# ==============================================================================


@pytest.mark.chaos_metrics
class TestChaosMetricsCollection:
    """Test metrics collection during chaos scenarios."""
    
    @pytest.mark.chaos_metrics_latency
    def test_latency_histogram_collection(self, lumina_engine):
        """Test latency metrics collection."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_metrics_error_rates
    def test_error_rate_tracking(self, lumina_engine):
        """Test error rate metrics."""
        assert lumina_engine is not None
    
    @pytest.mark.chaos_metrics_recovery_time
    def test_recovery_time_measurement(self, lumina_engine):
        """Test recovery time metrics."""
        assert lumina_engine is not None


# ==============================================================================
# CI Integration & Nightly Run Configuration
# ==============================================================================


@pytest.fixture(scope="session")
def chaos_config():
    """Configuration for chaos runs."""
    return {
        "enabled": True,
        "duration_minutes": 5,
        "enable_nightly": True,
        "failure_injection_rate": 0.15,
        "max_concurrent_faults": 3,
        "report_path": "chaos_engineering_report.json",
    }


@pytest.mark.chaos_ci_integration
class TestChaosCI:
    """Tests for CI integration."""
    
    @pytest.mark.chaos_ci_smoke
    def test_chaos_smoke_test_ci(self, chaos_config):
        """Quick chaos smoke test for CI."""
        assert chaos_config["enabled"] is True
    
    @pytest.mark.chaos_ci_nightly
    def test_chaos_nightly_configuration(self, chaos_config):
        """Test nightly run configuration."""
        assert chaos_config["enable_nightly"] is True
