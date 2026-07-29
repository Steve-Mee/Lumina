from lumina_core.birth.stage_scorecard import compute_stage_blocker, build_scorecard_payload
from lumina_core.birth.stage_blocker import compute_stage_blocker as blocker_fn

assert compute_stage_blocker is blocker_fn
print("ok", compute_stage_blocker.__name__, build_scorecard_payload.__name__)
