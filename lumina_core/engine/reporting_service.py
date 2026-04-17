from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
import numpy as np
import plotly.graph_objects as go

from .dashboard_service import DashboardService
from .lumina_engine import LuminaEngine
from .valuation_engine import ValuationEngine


class LuminaPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LUMINA v39 – Professional Trading Journal", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


@dataclass(slots=True)
class ReportingService:
    """Journaling and backtest reflection service backed by engine state."""

    engine: LuminaEngine
    dashboard_service: DashboardService
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("ReportingService requires a LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def generate_daily_journal(self) -> str | None:
        try:
            app = self._app()
            today = datetime.now().strftime("%Y-%m-%d")
            journal_dir = self.engine.config.journal_dir
            journal_dir.mkdir(parents=True, exist_ok=True)
            file_path = journal_dir / f"journal_{today}.html"

            trade_mode = self.engine.config.trade_mode.upper()
            html_content = f"""
        <html><head><title>LUMINA Journal {today}</title>
        <style>body{{font-family:Arial;background:#111;color:#0f0;}}</style></head><body>
        <h1>LUMINA v32 Daily Journal - {today}</h1>
        <h2>Account: {self.engine.account_equity:,.0f} | Mode: {trade_mode}</h2>
        <h3>Trades vandaag</h3>
        <table border="1" style="width:100%;border-collapse:collapse;">
        <tr><th>Tijd</th><th>Signal</th><th>PnL</th><th>Confluence</th><th>Reflection</th></tr>
        """
            for trade in self.engine.trade_log[-50:]:
                html_content += f"<tr><td>{trade.get('ts','')}</td><td>{trade.get('signal','')}</td><td>${trade.get('pnl',0):,.0f}</td><td>{trade.get('confluence',0):.2f}</td><td>{trade.get('reflection','')}</td></tr>"

            html_content += "</table><h3>Laatste reflections</h3><ul>"
            for ref in list(self.engine.trade_reflection_history)[-10:]:
                html_content += f"<li>{ref.get('ts','')} | PnL ${ref.get('pnl',0):,.0f} -> {ref.get('key_lesson','')}</li>"
            html_content += "</ul></body></html>"

            file_path.write_text(html_content, encoding="utf-8")
            print(f"📄 Journal opgeslagen -> {file_path}")
            return str(file_path)
        except Exception as exc:
            self._app().logger.error(f"Journal error: {exc}")
            return None

    def generate_professional_pdf_journal(self) -> str | None:
        app = self._app()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            journal_pdf_dir = self.engine.config.journal_pdf_dir
            journal_pdf_dir.mkdir(parents=True, exist_ok=True)
            filename = journal_pdf_dir / f"LUMINA_Journal_{today}.pdf"

            pdf = LuminaPDF()
            pdf.add_page()

            trade_mode = self.engine.config.trade_mode.upper()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, f"Daily Journal – {today} | Mode: {trade_mode}", new_x="LMARGIN", new_y="NEXT", align="C")
            pdf.set_font("Arial", "", 12)
            pdf.cell(
                0,
                8,
                f"Equity: ${self.engine.account_equity:,.0f} | Open PnL: ${self.engine.open_pnl:,.0f} | Realized PnL: ${self.engine.realized_pnl_today:,.0f}",
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )
            pdf.ln(10)

            if len(self.engine.equity_curve) > 10:
                fig = go.Figure(data=go.Scatter(y=self.engine.equity_curve, mode="lines", name="Equity"))
                fig.update_layout(title="Equity Curve", template="plotly_dark", height=400)
                temp_equity = Path("temp_equity.png")
                fig.write_image(str(temp_equity))
                pdf.image(str(temp_equity), x=10, y=pdf.get_y(), w=190)
                pdf.ln(85)
                temp_equity.unlink(missing_ok=True)

            summary = self.dashboard_service.generate_performance_summary()
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "Performance Summary", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Arial", "", 11)
            pdf.cell(
                0,
                6,
                f"Sharpe: {summary['sharpe']} | Winrate: {summary['winrate']:.1%} | Trades: {summary['trades']} | Avg PnL: ${summary.get('avg_pnl', 0)}",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.ln(10)

            heatmap_fig = self.dashboard_service.generate_strategy_heatmap()
            if heatmap_fig:
                temp_heatmap = Path("temp_heatmap.png")
                heatmap_fig.write_image(str(temp_heatmap))
                pdf.image(str(temp_heatmap), x=10, y=pdf.get_y(), w=190)
                pdf.ln(90)
                temp_heatmap.unlink(missing_ok=True)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "Laatste Trades", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Arial", "", 10)
            for trade in self.engine.trade_log[-15:]:
                pdf.cell(
                    0,
                    6,
                    f"{trade.get('ts','')} | {trade.get('signal','')} | PnL ${trade.get('pnl',0):,.0f} | Conf {trade.get('confluence',0):.2f}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            pdf.ln(10)

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, "Reflections & Lessons Learned", new_x="LMARGIN", new_y="NEXT")
            for ref in list(self.engine.trade_reflection_history)[-8:]:
                pdf.multi_cell(0, 6, f"{ref['ts']} | PnL ${ref['pnl']:,.0f} -> {ref.get('key_lesson','')}")

            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "WEEKLY REVIEW – Generated by LUMINA", new_x="LMARGIN", new_y="NEXT", align="C")
            recent_lessons = [r.get('key_lesson', '') for r in list(self.engine.trade_reflection_history)[-10:]]
            weekly_prompt = (
                "Schrijf een professionele, eerlijke weekly review. Geen emoties, alleen feiten en concrete verbeterpunten.\n"
                f"Week van {today}. Performance: Sharpe {summary['sharpe']}, "
                f"Winrate {summary['winrate']:.1%}, Max DD {summary.get('maxdd','N/A')}. "
                f"Laatste reflections: {json.dumps(recent_lessons)}"
            )
            local_engine = getattr(app, "local_inference_engine", None)
            if local_engine is not None and hasattr(local_engine, "infer"):
                review_resp = local_engine.infer(
                    weekly_prompt,
                    model_type="reasoning",
                    require_json=False,
                    max_tokens=500,
                )
                review_text = str(review_resp.get("content", "")).strip()
                if review_text:
                    pdf.multi_cell(0, 6, review_text)

            pdf.output(str(filename))
            print(f"📄 PROFESSIONAL PDF JOURNAL gegenereerd -> {filename}")
            return str(filename)
        except Exception as exc:
            app.logger.error(f"PDF journal error: {exc}")
            return None

    def auto_journal_daemon(self) -> None:
        while True:
            time.sleep(86400)
            if len(self.engine.ohlc_1min) > 500:
                self.generate_professional_pdf_journal()

    def run_auto_backtest(self, days: int = 5) -> dict[str, Any]:
        app = self._app()
        try:
            with self.engine.live_data_lock:
                df = self.engine.ohlc_1min.copy()

            bt_pnl: list[float] = []
            bt_position = 0
            bt_entry = 0.0
            min_confluence = float(self.engine.config.min_confluence)

            for i in range(60, len(df)):
                price = float(df["close"].iloc[i])
                dream_snapshot = self.engine.get_current_dream_snapshot()
                signal = dream_snapshot.get("signal", "HOLD")
                if bt_position == 0 and signal in ["BUY", "SELL"] and float(dream_snapshot.get("confluence_score", 0)) > min_confluence:
                    bt_position = 1 if signal == "BUY" else -1
                    bt_entry = price
                if bt_position != 0:
                    stop = float(dream_snapshot.get("stop", 0))
                    target = float(dream_snapshot.get("target", 0))
                    if (
                        (bt_position > 0 and price <= stop)
                        or (bt_position < 0 and price >= stop)
                        or (bt_position > 0 and price >= target)
                        or (bt_position < 0 and price <= target)
                    ):
                        pnl = self.valuation_engine.pnl_dollars(
                            symbol=str(self.engine.config.instrument),
                            entry_price=bt_entry,
                            exit_price=price,
                            side=bt_position,
                            quantity=1,
                        )
                        bt_pnl.append(pnl)
                        bt_position = 0

            if not bt_pnl:
                return {"sharpe": 0, "winrate": 0, "maxdd": 0, "trades": 0, "avg_pnl": 0}

            sharpe = (float(np.mean(bt_pnl)) / (float(np.std(bt_pnl)) + 1e-8)) * float(np.sqrt(252))
            winrate = float(np.mean(np.array(bt_pnl) > 0))
            if len(bt_pnl) > 1:
                equity = np.cumsum(bt_pnl)
                peak = np.maximum.accumulate(equity)
                drawdown = np.zeros_like(equity, dtype=float)
                valid = peak > 0
                drawdown[valid] = (peak[valid] - equity[valid]) / peak[valid]
                maxdd = float(np.max(drawdown) * 100)
            else:
                maxdd = 0.0
            return {
                "sharpe": round(sharpe, 2),
                "winrate": round(winrate, 3),
                "maxdd": round(maxdd, 1),
                "trades": len(bt_pnl),
                "avg_pnl": round(float(np.mean(bt_pnl)), 1),
            }
        except Exception as exc:
            app.logger.error(f"Backtest error: {exc}")
            return {"sharpe": 0, "winrate": 0, "maxdd": 0, "trades": 0, "avg_pnl": 0}

    async def backtest_reflection(self, backtest_results: dict[str, Any]):
        app = self._app()
        backtest_days = int(getattr(app, "BACKTEST_DAYS", 5))
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {"role": "system", "content": "Je bent een strenge trading-coach. Analyseer de backtest en stel concrete bible-updates voor. Geef ALLEEN JSON."},
                {
                    "role": "user",
                    "content": f"""Backtest resultaten (laatste {backtest_days} dagen):
Sharpe: {backtest_results['sharpe']}
Winrate: {backtest_results['winrate']:.1%}
Max DD: {backtest_results['maxdd']}%
Trades: {backtest_results['trades']}
Avg PnL: ${backtest_results['avg_pnl']}
Huidige bible evolvable_layer: {json.dumps(self.engine.evolvable_layer)}

Wat moet er verbeterd worden? Geef JSON met: reflection, suggested_bible_updates (dict)""",
                },
            ],
        }

        try:
            infer_json_fn = getattr(app, "infer_json", None)
            if not callable(infer_json_fn):
                return None

            ref = infer_json_fn(payload, timeout=25, context="backtest_reflection")
            if isinstance(ref, dict):
                if ref.get("suggested_bible_updates"):
                    self.engine.evolve_bible(ref["suggested_bible_updates"])
                self.engine.logger.info(f"Backtest reflection: {ref.get('reflection','')[:120]}")
                app.store_experience_to_vector_db(
                    context=f"Backtest Reflection: Sharpe {backtest_results['sharpe']}, Winrate {backtest_results['winrate']:.1%}",
                    metadata={"type": "backtest_reflection", "date": datetime.now().isoformat()},
                )
                return ref
        except Exception as exc:
            app.logger.error(f"Backtest reflection error: {exc}")
        return None

    def auto_backtest_daemon(self) -> None:
        app = self._app()
        backtest_days = int(getattr(app, "BACKTEST_DAYS", 5))
        while True:
            time.sleep(3600 * 4)
            if not app.is_market_open() and len(self.engine.ohlc_1min) > 1000:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 📈 Automated backtest gestart...")
                results = self.run_auto_backtest(backtest_days)
                app.asyncio.run(self.backtest_reflection(results))
