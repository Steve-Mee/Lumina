import sys
from pathlib import Path

from lumina_core.runtime_context import RuntimeContext

_repo_root = Path(__file__).resolve().parents[1]
_pkg_root = _repo_root / "lumina-bible"
if _pkg_root.exists() and str(_pkg_root) not in sys.path:
    sys.path.insert(0, str(_pkg_root))

from lumina_bible.workflows import dna_rewrite_daemon as _dna_rewrite_daemon
from lumina_bible.workflows import process_user_feedback as _process_user_feedback
from lumina_bible.workflows import reflect_on_trade as _reflect_on_trade


def reflect_on_trade(app: RuntimeContext, pnl_dollars: float, entry_price: float, exit_price: float, position_qty: int) -> None:
    _reflect_on_trade(app, pnl_dollars, entry_price, exit_price, position_qty)


def process_user_feedback(app: RuntimeContext, feedback_text: str, trade_data: dict | None = None) -> None:
    _process_user_feedback(app, feedback_text, trade_data)


def dna_rewrite_daemon(app: RuntimeContext) -> None:
    _dna_rewrite_daemon(app)
