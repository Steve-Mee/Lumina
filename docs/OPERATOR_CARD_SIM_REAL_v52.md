# OPERATOR CARD - SIM vs REAL v52

1. Pre-check: run safety gate -> python -m pytest -m safety_gate -q (must be green).
2. SIM mission: maximize learning; larger Kelly-driven sizing is expected.
3. REAL mission: capital preservation only; conservative sizing remains enforced.
4. REAL EOD no-new-trades: entries are blocked before session close window.
5. REAL EOD force-close: open positions are flattened near session close.
6. If any unknown runtime state appears: NO TRADING (fail-closed).
7. Validate SIM summary after release: mode=sim, evolution_proposals elevated, no severe PnL regression.
8. Validate REAL dry route: headless real/live smoke before any real capital session.
9. Emergency action: stop process, switch to paper path, rerun safety gate.
10. Resume only after green safety gate + headless checks + operator sign-off.
