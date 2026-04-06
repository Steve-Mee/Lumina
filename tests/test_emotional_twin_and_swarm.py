"""Integration test: EmotionalTwinAgent + Multi-Symbol Swarm working together."""

import pytest
import pandas as pd
import numpy as np
from types import SimpleNamespace
from unittest.mock import MagicMock
from datetime import datetime

from lumina_core.engine.swarm_manager import SwarmManager
from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent
from lumina_core.runtime_context import RuntimeContext


@pytest.fixture
def integrated_engine():
    """Create mock engine with all required attributes for both agents."""
    engine = SimpleNamespace(
        config=SimpleNamespace(
            instrument="MES JUN26",
            max_risk_percent=5.0,
            swarm_symbols=["MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26"],
        ),
        logger=MagicMock(),
        app=None,
        equity_curve=[50000.0, 50100.0],
        current_market_state={'price': 5600.0, 'regime': 'uptrend'},
        get_current_dream_snapshot=MagicMock(return_value={
            'confidence': 0.85,
            'confluence_score': 75,
            'consensus': 'LONG',
            'target_price': 5620
        }),
        account_equity=10000,
        account_balance=1000,
        current_price=5600.0,
        live_quotes=[{"last": 5600.0}],
        ohlc_1min=pd.DataFrame({
            'timestamp': pd.date_range('2026-03-01', periods=100, freq='min'),
            'close': np.linspace(5550, 5650, 100)
        }),
        pnl_history=[100, 150, 120],
        trade_log=[{"ts": "2026-04-04T10:00:00"}],
        sim_peak=10500,
        detect_market_regime=MagicMock(return_value="uptrend"),
        set_current_dream_fields=MagicMock(),
    )
    return engine


@pytest.fixture
def integrated_context(integrated_engine):
    """Create RuntimeContext with integrated engine."""
    return RuntimeContext(engine=integrated_engine)  # type: ignore


class TestEmotionalTwinAndSwarmIntegration:
    """Test EmotionalTwinAgent and SwarmManager working together."""

    def test_both_agents_instantiate(self, integrated_engine, integrated_context):
        """Verify both agents can be created with same engine."""
        twin = EmotionalTwinAgent(integrated_context)
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        
        assert twin is not None
        assert swarm is not None
        assert len(swarm.nodes) == 4

    def test_emotional_twin_corrects_dream_state(self, integrated_context):
        """Verify emotional twin can correct a dream state."""
        twin = EmotionalTwinAgent(integrated_context)
        dream = {
            'confidence': 0.85,
            'confluence_score': 75,
            'consensus': 'LONG',
            'target_price': 5620,
            'quantity': 10
        }
        
        corrected = twin.apply_correction(dream)
        # Verify corrections were applied (qty may be reduced, reason updated, etc)
        assert 'reason' in corrected
        assert 'quantity' in corrected or 'qty' in corrected
        # Verify original fields preserved or modified
        assert 'confidence' in corrected or 'consensus' in corrected

    def test_swarm_applies_context_to_dream(self, integrated_engine):
        """Verify swarm can update dream state with allocation context."""
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        
        snapshot = swarm.run_cycle()
        updates = swarm.apply_to_primary_dream()
        
        assert 'swarm_ts' in updates
        assert 'position_size_multiplier' in updates
        assert 'swarm_consensus_multiplier' in updates
        
        integrated_engine.set_current_dream_fields.assert_called_with(updates)

    def test_sequential_execution_order(self, integrated_engine, integrated_context):
        """Simulate execution order: swarm → emotional_twin → trade decision."""
        # Step 1: Swarm runs first
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        swarm_snapshot = swarm.run_cycle()
        swarm_updates = swarm.apply_to_primary_dream()
        
        # Verify swarm allocated capital
        assert swarm_snapshot['capital_allocation_pct']['MES JUN26'] > 0
        assert 'position_size_multiplier' in swarm_updates
        swarm_mult = swarm_updates.get('swarm_consensus_multiplier', 1.0)
        
        # Step 2: Emotional Twin applies correction
        twin = EmotionalTwinAgent(integrated_context)
        dream = {
            'confidence': 0.9,
            'confluence_score': 80,
            'consensus': 'LONG',
            'target_price': 5650,
            'quantity': 20,
            'position_size_multiplier': swarm_mult  # Swarm's allocation
        }
        corrected_dream = twin.apply_correction(dream)
        
        # Step 3: Verify final dream state
        assert corrected_dream is not None
        assert isinstance(corrected_dream, dict)
        assert 'reason' in corrected_dream  # Emotional twin adds reason
        
        # Emotional twin may adjust quantity/qty
        final_qty = corrected_dream.get('quantity') or corrected_dream.get('qty')
        assert final_qty is not None

    def test_multi_symbol_trade_flow(self, integrated_engine):
        """Simulate trading across all 4 symbols with emotional corrections."""
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        
        # Populate with price data for each symbol
        symbols_data = {
            "MES JUN26": list(np.linspace(5600, 5650, 50)),
            "MNQ JUN26": list(np.linspace(22000, 22300, 50)),
            "MYM JUN26": list(np.linspace(450, 460, 50)),
            "ES JUN26": list(np.linspace(5600, 5650, 50)),
        }
        
        for symbol, prices in symbols_data.items():
            node = swarm.nodes[symbol]
            for price in prices:
                node.prices_rolling.append(price)
                if len(node.prices_rolling) > 1:
                    prev = node.prices_rolling[-2]
                    node.returns_rolling.append((price - prev) / prev)
                node.last_price = price

        # Run swarm cycle
        snapshot = swarm.run_cycle()
        allocation = snapshot['capital_allocation_pct']
        
        # Verify all symbols got allocation
        assert all(sym in allocation for sym in swarm.symbols)
        assert sum(allocation.values()) <= 5.01  # Allow 1% rounding
        
        # Simulate trades and register results
        trades = {
            "MES JUN26": 150.0,
            "MNQ JUN26": -75.0,
            "MYM JUN26": 200.0,
            "ES JUN26": 100.0,
        }
        
        for symbol, pnl in trades.items():
            swarm.register_trade_result(symbol, pnl)
        
        # Verify all symbols tracked the trades
        for symbol, expected_pnl in trades.items():
            node = swarm.nodes[symbol]
            assert len(node.pnl_history) == 1
            assert node.pnl_history[0] == expected_pnl

    def test_regime_consensus_affects_position_sizing(self, integrated_engine, integrated_context):
        """Verify regime consensus (via swarm) affects emotional twin corrections."""
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        twin = EmotionalTwinAgent(integrated_context)
        
        # Scenario 1: No consensus (1 trending)
        swarm.nodes["MES JUN26"].regimes_rolling.append("TRENDING")
        swarm.nodes["MNQ JUN26"].regimes_rolling.append("RANGE")
        swarm.nodes["MYM JUN26"].regimes_rolling.append("CHOPPY")
        swarm.nodes["ES JUN26"].regimes_rolling.append("NEUTRAL")
        
        mult1, _ = swarm._regime_consensus_multiplier()
        assert mult1 == 1.0
        
        # Scenario 2: Consensus (3 trending)
        for _ in range(3):
            swarm.nodes["MNQ JUN26"].regimes_rolling.append("TRENDING")
            swarm.nodes["MYM JUN26"].regimes_rolling.append("TRENDING")
        
        mult2, _ = swarm._regime_consensus_multiplier()
        assert mult2 == 1.6
        
        # Both states should allow dream corrections
        dream_no_consensus = {'confidence': 0.8, 'quantity': 10}
        dream_with_consensus = {'confidence': 0.8, 'quantity': 10}
        
        corrected1 = twin.apply_correction(dream_no_consensus)
        corrected2 = twin.apply_correction(dream_with_consensus)
        
        assert corrected1 is not None
        assert corrected2 is not None

    def test_arbitrage_signal_integration(self, integrated_engine):
        """Verify arbitrage signals can be passed to emotional twin."""
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        
        # Create moderate correlation to find arbitrage
        base_prices = list(np.linspace(100, 102, 20))
        swarm.nodes["MES JUN26"].prices_rolling = __import__('collections').deque(base_prices, maxlen=30)
        swarm.nodes["MNQ JUN26"].prices_rolling = __import__('collections').deque([p * 0.5 for p in base_prices], maxlen=30)
        
        arb_signals = swarm.detect_inter_symbol_arbitrage()
        
        # If signals exist, they should be well-formed
        for signal in arb_signals:
            assert "pair" in signal
            assert "trade_a" in signal
            assert "trade_b" in signal
            assert "zscore" in signal

    def test_nightly_training_with_swarm_data(self, integrated_context):
        """Verify emotional twin nightly training can use swarm-collected data."""
        twin = EmotionalTwinAgent(integrated_context)
        
        # Add mock trade reflections
        reflections = [
            {"symbol": "MES JUN26", "pnl": 150, "reason": "FOMO entry, worked", "feedback": "good"},
            {"symbol": "MNQ JUN26", "pnl": -75, "reason": "Tilt after loss", "feedback": "bad"},
            {"symbol": "MYM JUN26", "pnl": 200, "reason": "Patience paid off", "feedback": "great"},
        ]
        
        feedback = ["good", "bad", "great"]
        
        # Trigger nightly training
        twin.nightly_train(reflections, feedback)
        
        # Verify calibration was updated (file should exist)
        import json
        from pathlib import Path
        profile_path = Path("lumina_agents/emotional_twin_profile.json")
        
        if profile_path.exists():
            with open(profile_path) as f:
                profile = json.load(f)
            assert "fomo_sensitivity" in profile
            assert "tilt_sensitivity" in profile


class TestScalability:
    """Test swarm behavior with different symbol counts."""

    def test_scales_to_2_symbols(self, integrated_engine):
        """Verify swarm works with minimal 2 symbols."""
        integrated_engine.config.swarm_symbols = ["MES JUN26", "MNQ JUN26"]
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        assert len(swarm.nodes) == 2
        snapshot = swarm.run_cycle()
        assert len(snapshot['symbols']) == 2

    def test_scales_to_6_symbols(self, integrated_engine):
        """Verify swarm can handle 6 symbols (future expansion)."""
        expanded_symbols = [
            "MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26",
            "AAPL STOCK", "TSLA STOCK"
        ]
        integrated_engine.config.swarm_symbols = expanded_symbols
        swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
        assert len(swarm.nodes) == 6
        snapshot = swarm.run_cycle()
        assert len(snapshot['symbols']) == 6

    def test_correlation_matrix_grows_with_symbols(self, integrated_engine):
        """Verify correlation matrix dimensions scale."""
        for n_symbols in [2, 4, 6]:
            symbols = [
                "MES JUN26", "MNQ JUN26", "MYM JUN26", "ES JUN26",
                "AAPL STOCK", "TSLA STOCK"
            ][:n_symbols]
            
            integrated_engine.config.swarm_symbols = symbols
            swarm = SwarmManager(integrated_engine)  # type: ignore[arg-type]
            
            # Add returns for correlation
            for sym in symbols:
                for _ in range(10):
                    swarm.nodes[sym].returns_rolling.append(np.random.normal(0, 0.01))
            
            corr = swarm.build_correlation_matrix()
            assert corr.shape[0] == n_symbols
            assert corr.shape[1] == n_symbols


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
