"""Primary Gym RL package; ``training_reward`` / shaped metrics also exist in ``lumina_core.engine.rl`` (Meta-RL)—never on broker economic payloads."""

from lumina_core.rl.gym_environment import RLConfig, RLTradingEnvironment
from lumina_core.rl.observation_builder import OBSERVATION_DIM, build_observation_vector

__all__ = ["RLConfig", "RLTradingEnvironment", "OBSERVATION_DIM", "build_observation_vector"]
