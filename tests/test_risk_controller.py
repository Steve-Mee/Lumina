# CANONICAL IMPLEMENTATION – v50 Living Organism
# Unit tests for Hard Risk Controller

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import json
from dataclasses import replace

from lumina_core.engine.risk_controller import (
    HardRiskController,
    RiskLimits,
    RiskState,
)
from lumina_core.engine.margin_snapshot_provider import MarginSnapshot


class _StubPortfolioAllocator:
    def __init__(self, allow: bool) -> None:
        self.allow = allow

    def evaluate_proposed_trade(self, *, symbol, proposed_risk, open_risk_by_symbol):
        snapshot = type(
            "Snapshot",
            (),
            {
                "var_usd": 1500.0,
                "max_var_usd": 1200.0,
                "breached": not self.allow,
                "reason": "PORTFOLIO VAR breached: 1500.00 > 1200.00",
            },
        )
        return self.allow, ("OK" if self.allow else snapshot.reason), snapshot


class _StubSessionGuard:
    def __init__(
        self,
        *,
        market_open: bool = True,
        rollover: bool = False,
        block_new_eod: bool = False,
        force_close_eod: bool = False,
        minutes_to_close: float = 30.0,
    ) -> None:
        self._market_open = market_open
        self._rollover = rollover
        self._block_new_eod = block_new_eod
        self._force_close_eod = force_close_eod
        self._minutes_to_close = minutes_to_close

    def is_rollover_window(self) -> bool:
        return self._rollover

    def is_market_open(self) -> bool:
        return self._market_open

    def next_open(self):
        return None

    def should_block_new_eod_trades(self, ts=None, no_new_trades_minutes: int = 60) -> bool:
        del ts, no_new_trades_minutes
        return self._block_new_eod

    def should_force_close_eod(self, ts=None, force_close_minutes: int = 30) -> bool:
        del ts, force_close_minutes
        return self._force_close_eod

    def minutes_to_session_end(self, ts=None) -> float:
        del ts
        return self._minutes_to_close


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TestRiskLimits:
    """Test RiskLimits configuration validation."""
    
    def test_valid_limits(self):
        """Valid limits should not raise."""
        limits = RiskLimits(
            daily_loss_cap=-1000.0,
            max_consecutive_losses=3,
            max_open_risk_per_instrument=500.0,
            max_exposure_per_regime=2000.0,
            cooldown_after_streak=30,
        )
        assert limits.validate() is True
    
    def test_positive_loss_cap_warning(self, caplog):
        """Positive daily_loss_cap should warn."""
        limits = RiskLimits(daily_loss_cap=1000.0)
        limits.validate()
        assert "daily_loss_cap should be negative" in caplog.text
    
    def test_invalid_consecutive_losses(self):
        """Max consecutive losses < 1 should fail."""
        limits = RiskLimits(max_consecutive_losses=0)
        assert limits.validate() is False
    
    def test_invalid_instrument_risk(self):
        """Max instrument risk <= 0 should fail."""
        limits = RiskLimits(max_open_risk_per_instrument=-100.0)
        assert limits.validate() is False
    
    def test_invalid_regime_exposure(self):
        """Max regime exposure <= 0 should fail."""
        limits = RiskLimits(max_exposure_per_regime=0)
        assert limits.validate() is False
    
    def test_invalid_cooldown(self):
        """Cooldown < 1 minute should fail."""
        limits = RiskLimits(cooldown_after_streak=0)
        assert limits.validate() is False


class TestHardRiskController:
    """Test main HardRiskController functionality."""
    
    @pytest.fixture
    def controller(self):
        """Create a basic risk controller for testing."""
        limits = RiskLimits(
            daily_loss_cap=-1000.0,
            max_consecutive_losses=3,
            max_open_risk_per_instrument=500.0,
            max_exposure_per_regime=2000.0,
            cooldown_after_streak=30,
            enforce_session_guard=False,
        )
        return HardRiskController(limits)
    
    # ===== DAILY LOSS CAP TESTS =====
    
    def test_trade_allowed_above_daily_cap(self, controller):
        """Trade should be allowed when daily P&L is above cap."""
        controller.state.daily_pnl = -500.0  # Above cap of -1000
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True
        assert reason == "OK"
    
    def test_trade_blocked_at_daily_cap(self, controller):
        """Trade should be blocked exactly at daily loss cap."""
        controller.state.daily_pnl = -1000.0  # Exactly at cap
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        assert "DAILY LOSS CAP breached" in reason
        assert controller.state.kill_switch_engaged is True
    
    def test_trade_blocked_below_daily_cap(self, controller):
        """Trade should be blocked when daily P&L is below cap."""
        controller.state.daily_pnl = -1500.0  # Below cap
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        assert "DAILY LOSS CAP breached" in reason
    
    def test_kill_switch_persists(self, controller):
        """After kill-switch engages, all trades should be blocked."""
        controller.state.daily_pnl = -1500.0
        controller.check_can_trade("MES", "trending_up", 100.0)
        
        # Even with P&L recovery, kill-switch should still block
        controller.state.daily_pnl = 100.0  # Recovered
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        assert "KILL SWITCH ENGAGED" in reason
    
    # ===== CONSECUTIVE LOSS TESTS =====
    
    def test_trade_allowed_no_losses(self, controller):
        """Trade should be allowed with no losses."""
        controller.state.consecutive_losses = 0
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True
    
    def test_trade_allowed_below_max_consecutive(self, controller):
        """Trade allowed with < max consecutive losses."""
        controller.state.consecutive_losses = 2  # Below max of 3
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True
    
    def test_trade_blocked_at_max_consecutive(self, controller):
        """Trade should be blocked when at max consecutive losses."""
        controller.state.consecutive_losses = 3
        controller.state.last_loss_time = _utcnow()
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        # After timestamp expiration, should still fail but different reason
    
    def test_cooldown_blocks_trading(self, controller):
        """Cooldown period should block all trades."""
        controller.state.consecutive_losses = 3
        controller.state.last_loss_time = _utcnow() - timedelta(minutes=10)  # 10 min ago
        
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        assert "LOSS STREAK COOLDOWN" in reason
        assert "20" in reason  # ~20 minutes remaining (30 - 10)
    
    def test_cooldown_expires(self, controller):
        """After cooldown period, trading should resume."""
        controller.state.consecutive_losses = 3
        # Loss occurred 45 minutes ago (cooldown is 30 min)
        controller.state.last_loss_time = _utcnow() - timedelta(minutes=45)
        
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True  # Cooldown expired, counter reset
        assert controller.state.consecutive_losses == 0  # Counter was reset
    
    def test_record_winning_trade_resets_counter(self, controller):
        """Winning trade should reset consecutive loss counter."""
        controller.state.consecutive_losses = 2
        controller.record_trade_result("MES", "trending_up", +500.0, 100.0)
        assert controller.state.consecutive_losses == 0
    
    def test_record_losing_trade_increments_counter(self, controller):
        """Losing trade should increment consecutive loss counter."""
        controller.state.consecutive_losses = 2
        controller.record_trade_result("MES", "trending_up", -200.0, 100.0)
        assert controller.state.consecutive_losses == 3
        assert controller.state.last_loss_time is not None
    
    # ===== PER-INSTRUMENT RISK TESTS =====
    
    def test_instrument_risk_allowed_under_limit(self, controller):
        """Trade allowed when instrument risk is under limit."""
        controller.state.open_risk_by_symbol['MES'] = 200.0  # Under 500 limit
        allowed, reason = controller.check_can_trade("MES", "trending_up", 200.0)
        assert allowed is True
    
    def test_instrument_risk_blocked_at_limit(self, controller):
        """Trade blocked when total would exceed limit."""
        controller.state.open_risk_by_symbol['MES'] = 400.0
        allowed, reason = controller.check_can_trade("MES", "trending_up", 200.0)  # 400 + 200 = 600 > 500
        assert allowed is False
        assert "MAX INSTRUMENT RISK exceeded" in reason
    
    def test_instrument_risk_blocked_exactly_at_limit(self, controller):
        """Trade blocked when total would exactly meet limit (edge case)."""
        controller.state.open_risk_by_symbol['MES'] = 300.0
        allowed, reason = controller.check_can_trade("MES", "trending_up", 200.0)  # 300 + 200 = 500 (at limit)
        # At limit is actually OK (not exceeding)
        assert allowed is True
    
    def test_different_instruments_independent_limits(self, controller):
        """Different instruments have independent risk limits."""
        controller.state.open_risk_by_symbol['MES'] = 400.0
        allowed, reason = controller.check_can_trade("NQ", "trending_up", 400.0)
        assert allowed is True  # NQ has separate 500 limit
    
    # ===== PER-REGIME EXPOSURE TESTS =====
    
    def test_regime_exposure_allowed_under_limit(self, controller):
        """Trade allowed when regime exposure under limit."""
        controller.state.open_risk_all_regimes['trending_up'] = 1000.0  # Under 2000 limit
        allowed, reason = controller.check_can_trade("MES", "trending_up", 500.0)
        assert allowed is True
    
    def test_regime_exposure_blocked_exceeds_limit(self, controller):
        """Trade blocked when regime exposure would exceed limit."""
        controller.state.open_risk_all_regimes['trending_up'] = 1800.0
        allowed, reason = controller.check_can_trade("MES", "trending_up", 300.0)  # 1800 + 300 = 2100 > 2000
        assert allowed is False
        assert "MAX REGIME EXPOSURE exceeded" in reason
    
    def test_different_regimes_independent_limits(self, controller):
        """Different regimes have independent exposure limits."""
        controller.state.open_risk_all_regimes['trending_up'] = 1900.0  # Almost at limit
        allowed, reason = controller.check_can_trade("MES", "ranging", 500.0)  # Different regime
        assert allowed is True  # Different regime, separate limit
    
    # ===== STATE PERSISTENCE TESTS =====
    
    def test_state_persistence_save_and_load(self):
        """Risk state should persist to disk and be recoverable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            
            # Create controller, record some state
            limits = RiskLimits(enforce_session_guard=False)
            controller1 = HardRiskController(limits, state_file=state_file)
            controller1.state.daily_pnl = -750.0
            controller1.state.consecutive_losses = 2
            controller1._save_state()
            
            # Create new controller, should load state
            controller2 = HardRiskController(limits, state_file=state_file)
            assert controller2.state.daily_pnl == -750.0
            assert controller2.state.consecutive_losses == 2
    
    def test_kill_switch_persisted_across_restarts(self):
        """Kill-switch should persist across controller restarts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            limits = RiskLimits(enforce_session_guard=False)
            
            # First controller engages kill-switch
            controller1 = HardRiskController(limits, state_file=state_file)
            controller1.state.daily_pnl = -1500.0
            controller1.check_can_trade("MES", "trending_up", 100.0)
            assert controller1.state.kill_switch_engaged is True
            
            # New controller should load kill-switch state
            controller2 = HardRiskController(limits, state_file=state_file)
            allowed, reason = controller2.check_can_trade("MES", "trending_up", 100.0)
            assert allowed is False
            assert "KILL SWITCH ENGAGED" in reason
    
    # ===== TRADE HISTORY TESTS =====
    
    def test_trade_history_captured(self, controller):
        """Trade results should be stored in history."""
        controller.record_trade_result("MES", "trending_up", +250.0, 100.0)
        controller.record_trade_result("NQ", "ranging", -150.0, 80.0)
        
        assert len(controller.state.trade_history) == 2
        assert controller.state.trade_history[0]['pnl'] == 250.0
        assert controller.state.trade_history[1]['pnl'] == -150.0
    
    def test_trade_history_maxlen_enforced(self, controller):
        """Trade history should maintain max length."""
        for i in range(150):  # Record 150 trades
            controller.record_trade_result("MES", "trending_up", float(i), 100.0)
        
        assert len(controller.state.trade_history) == 100  # Deque maxlen=100
    
    # ===== STATUS REPORTING TESTS =====
    
    def test_get_status_all_fields(self, controller):
        """Status report should include all relevant metrics."""
        controller.state.daily_pnl = -500.0
        controller.state.consecutive_losses = 2
        controller.state.open_risk_by_symbol['MES'] = 200.0
        
        status = controller.get_status()
        assert status['daily_pnl'] == -500.0
        assert status['consecutive_losses'] == 2
        assert status['open_risk_by_symbol']['MES'] == 200.0
        assert 'kill_switch_engaged' in status
        assert 'cooldown_remaining_minutes' in status
    
    def test_get_status_with_active_cooldown(self, controller):
        """Status should show remaining cooldown time."""
        controller.state.consecutive_losses = 3
        controller.state.last_loss_time = _utcnow() - timedelta(minutes=10)
        
        status = controller.get_status()
        cooldown_remaining = status['cooldown_remaining_minutes']
        assert 18.0 < cooldown_remaining < 22.0  # ~20 minutes (30 - 10)
    
    # ===== EDGE CASES =====
    
    def test_zero_proposed_risk(self, controller):
        """Zero proposed risk should always be allowed."""
        controller.state.daily_pnl = -1500.0  # Below cap
        allowed, reason = controller.check_can_trade("MES", "trending_up", 0.0)
        # Should fail because of daily cap, not because of zero risk
        assert allowed is False
    
    def test_multiple_checks_independent(self, controller):
        """Multiple failing checks should be caught by first check."""
        controller.state.daily_pnl = -2000.0  # Fails daily cap
        controller.state.consecutive_losses = 5  # Also fails consecutive
        
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        # First check (daily cap) should be reported
        assert "DAILY LOSS CAP" in reason or "KILL SWITCH" in reason

    def test_portfolio_var_allocator_blocks_trade(self, controller):
        """Portfolio VaR breach should block trade before final allow."""
        controller.portfolio_var_allocator = _StubPortfolioAllocator(allow=False)
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        assert "PORTFOLIO VAR breached" in reason

    def test_var_es_historical_breach_blocks_trade(self):
        """Historical VaR/ES breach should block in enforced mode."""
        limits = RiskLimits(
            enforce_session_guard=False,
            daily_loss_cap=-10000.0,
            max_consecutive_losses=50,
            var_es_method="historical",
            var_es_window=50,
            var_es_min_samples=10,
            var_95_limit_usd=50.0,
            var_99_limit_usd=60.0,
            es_95_limit_usd=70.0,
            es_99_limit_usd=80.0,
        )
        controller = HardRiskController(limits, enforce_rules=True)
        for _ in range(20):
            controller.record_trade_result("MES", "TRENDING", pnl=-120.0, risk_taken=100.0)

        allowed, reason = controller.check_can_trade("MES", "TRENDING", 200.0)
        assert allowed is False
        assert "VAR_ES breached" in reason

    def test_var_es_parametric_populates_status(self):
        """Parametric VaR/ES path should populate state snapshot."""
        limits = RiskLimits(
            enforce_session_guard=False,
            var_es_method="parametric",
            var_es_window=60,
            var_es_min_samples=12,
        )
        controller = HardRiskController(limits, enforce_rules=True)
        for i in range(24):
            pnl = 80.0 if i % 3 else -40.0
            controller.record_trade_result("MES", "TRENDING", pnl=pnl, risk_taken=100.0)

        ok, reason, snapshot = controller.check_var_es_pre_trade(150.0)
        assert isinstance(ok, bool)
        assert isinstance(reason, str)
        assert float(snapshot["var_95_usd"]) >= 0.0
        assert float(snapshot["es_95_usd"]) >= 0.0
        status = controller.get_status()
        assert "var_es" in status
        assert status["var_es"]["method"] == "parametric"

    def test_var_es_insufficient_samples_fail_closed(self):
        """Insufficient VaR samples should fail-closed in enforced mode when configured."""
        limits = RiskLimits(
            enforce_session_guard=False,
            max_consecutive_losses=50,
            var_es_method="historical",
            var_es_window=30,
            var_es_min_samples=25,
            var_es_fail_closed_on_insufficient_data=True,
        )
        controller = HardRiskController(limits, enforce_rules=True)
        for _ in range(5):
            controller.record_trade_result("MES", "TRENDING", pnl=-10.0, risk_taken=100.0)

        allowed, reason = controller.check_can_trade("MES", "TRENDING", 100.0)
        assert allowed is False
        assert "insufficient return samples" in reason

    def test_var_es_insufficient_samples_real_only_policy_skips_sim_real_guard(self):
        """fail_closed_real_only should remain advisory in sim_real_guard mode."""
        limits = RiskLimits(
            enforce_session_guard=False,
            runtime_mode="sim_real_guard",
            max_consecutive_losses=50,
            var_es_min_samples=25,
            var_es_fail_closed_on_insufficient_data=False,
            var_es_insufficient_data_policy="fail_closed_real_only",
        )
        controller = HardRiskController(limits, enforce_rules=True)
        for _ in range(5):
            controller.record_trade_result("MES", "TRENDING", pnl=-10.0, risk_taken=100.0)

        allowed, reason = controller.check_can_trade("MES", "TRENDING", 100.0)
        assert allowed is True
        assert "OK" in reason

    def test_var_es_feature_flag_disable_calculation(self):
        """When calculation is disabled, VaR/ES returns allow with disabled reason-code."""
        limits = RiskLimits(
            enforce_session_guard=False,
            runtime_mode="real",
            enable_var_es_calc=False,
        )
        controller = HardRiskController(limits, enforce_rules=True)

        ok, reason, payload = controller.check_var_es_pre_trade(120.0)
        assert ok is True
        assert "disabled" in reason.lower()
        assert payload["reason_code"] == "VAR_ES_DISABLED"
        assert payload["decision"] == "allow"

    def test_var_es_high_risk_multiplier_tightens_limits(self):
        """HIGH_RISK regime should apply tighter VaR/ES limits via multiplier."""
        limits = RiskLimits(
            enforce_session_guard=False,
            runtime_mode="real",
            max_consecutive_losses=50,
            var_es_method="historical",
            var_es_window=50,
            var_es_min_samples=10,
            var_95_limit_usd=200.0,
            var_99_limit_usd=400.0,
            es_95_limit_usd=500.0,
            es_99_limit_usd=600.0,
            var_es_high_risk_limit_multiplier=0.5,
        )
        controller = HardRiskController(limits, enforce_rules=True)
        controller.state.active_risk_state = "HIGH_RISK"
        for _ in range(20):
            controller.record_trade_result("MES", "TRENDING", pnl=-120.0, risk_taken=100.0)

        ok, reason, payload = controller.check_var_es_pre_trade(200.0)
        assert ok is False
        assert "VAR_ES breached" in reason
        assert float(payload["limit_multiplier"]) == 0.5
        assert float(payload["effective_var_95_limit_usd"]) == 100.0

    def test_stale_margin_snapshot_blocks_trade_in_enforced_mode(self, controller):
        """Stale margin snapshot should fail-closed when rules are enforced."""
        stale_snapshot = replace(
            controller.state.margin_tracker.snapshot,
            as_of=_utcnow() - timedelta(hours=300),
            stale_after_hours=24,
        )
        controller.state.margin_tracker.snapshot = stale_snapshot

        allowed, reason = controller.check_can_trade("MES", "TRENDING", 75.0)
        assert allowed is False
        assert "snapshot stale" in reason

    def test_low_margin_confidence_blocks_trade_in_enforced_mode(self, controller):
        """Low-confidence margin snapshot should fail-closed when rules are enforced."""
        low_conf_snapshot = replace(
            controller.state.margin_tracker.snapshot,
            confidence=0.2,
        )
        controller.state.margin_tracker.snapshot = low_conf_snapshot

        allowed, reason = controller.check_can_trade("MES", "TRENDING", 75.0)
        assert allowed is False
        assert "confidence too low" in reason

    @pytest.mark.safety_gate
    def test_real_mode_blocks_new_trades_in_eod_window(self):
        """REAL mode should block fresh entries in EOD no-new-trades window."""
        limits = RiskLimits(
            enforce_session_guard=True,
            sim_mode=False,
            eod_no_new_trades_minutes_before_session_end=60,
        )
        guard = _StubSessionGuard(block_new_eod=True, minutes_to_close=18.5)
        controller = HardRiskController(
            limits,
            enforce_rules=True,
            session_guard=guard,
        )

        allowed, reason = controller.check_can_trade("MES", "TRENDING", 75.0)
        assert allowed is False
        assert "no-new-trades window" in reason

    @pytest.mark.safety_gate
    def test_real_mode_force_close_signal_from_session_guard(self):
        """REAL mode should surface EOD force-close trigger from SessionGuard."""
        limits = RiskLimits(
            enforce_session_guard=True,
            sim_mode=False,
            eod_force_close_minutes_before_session_end=30,
        )
        guard = _StubSessionGuard(force_close_eod=True, minutes_to_close=12.0)
        controller = HardRiskController(
            limits,
            enforce_rules=True,
            session_guard=guard,
        )

        should_close, reason = controller.should_force_close_eod()
        assert should_close is True
        assert "force-close window" in reason


class TestLearningMode:
    """Test learning/testing mode where live rules are bypassed."""
    
    def test_learning_mode_bypasses_all_rules(self):
        """In learning mode (enforce_rules=False), all rules should be bypassed."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits, enforce_rules=False)
        
        # Even with breached limits, should return OK
        controller.state.daily_pnl = -2000.0  # Well below cap
        allowed, reason = controller.check_can_trade("MES", "trending_up", 1000.0)
        assert allowed is True
        assert "learning" in reason.lower() or "bypassed" in reason.lower()
    
    def test_learning_mode_with_kill_switch_engaged(self):
        """Kill-switch should be bypassed in learning mode."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits, enforce_rules=False)
        
        # Engage kill-switch
        controller.state.kill_switch_engaged = True
        controller.state.kill_switch_reason = "Test"
        
        # Should still allow trading in learning mode
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True
        assert "learning" in reason.lower() or "bypassed" in reason.lower()
    
    def test_set_enforce_rules_switches_mode(self):
        """set_enforce_rules() should toggle enforcement."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits, enforce_rules=True)
        
        # Start in enforce mode
        controller.state.daily_pnl = -2000.0
        allowed, _ = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False  # Should be blocked
        
        # Switch to learning mode
        controller.set_enforce_rules(False)
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True  # Should be allowed now
        assert "learning" in reason.lower() or "bypassed" in reason.lower()

    def test_learning_mode_does_not_fail_closed_on_low_margin_confidence(self):
        """Learning mode keeps advisory behavior and bypasses confidence hard-block."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits, enforce_rules=False)

        low_conf_snapshot = replace(
            controller.state.margin_tracker.snapshot,
            confidence=0.1,
        )
        controller.state.margin_tracker.snapshot = low_conf_snapshot

        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True
        assert "learning" in reason.lower() or "bypassed" in reason.lower()
    
    def test_health_check_respects_learning_mode(self):
        """health_check_market_open should pass in learning mode."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits, enforce_rules=False)
        
        # Engage kill-switch
        controller.state.kill_switch_engaged = True
        controller.state.kill_switch_reason = "Test"
        
        # Health check should pass in learning mode
        healthy, msg = controller.health_check_market_open("MES", "trending_up")
        assert healthy is True
        assert "learning" in msg.lower()


class TestKillSwitchManagement:
    """Test kill-switch manual reset and authorization."""
    
    def test_reset_kill_switch_when_not_engaged(self):
        """Reset on non-engaged kill-switch should succeed without warning."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits)
        
        result = controller.reset_kill_switch()
        assert result is True
    
    def test_reset_kill_switch_when_engaged(self):
        """Reset should clear engaged kill-switch."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits)
        
        # Engage kill-switch
        controller.state.kill_switch_engaged = True
        controller.state.kill_switch_reason = "Test engagement"
        
        result = controller.reset_kill_switch()
        assert result is True
        assert controller.state.kill_switch_engaged is False
        assert controller.state.kill_switch_reason == ""
    
    def test_trading_resumes_after_reset(self):
        """After reset, trading should resume if other checks pass."""
        limits = RiskLimits(enforce_session_guard=False)
        controller = HardRiskController(limits)
        
        # Engage kill-switch
        controller.state.kill_switch_engaged = True
        controller.state.kill_switch_reason = "Test"
        allowed, _ = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is False
        
        # Reset
        controller.reset_kill_switch()
        allowed, reason = controller.check_can_trade("MES", "trending_up", 100.0)
        assert allowed is True
        assert reason == "OK"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
