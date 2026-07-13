"""LUMINA operator domain package (core, services — no Streamlit UI).

Entry points:
  - ``python -m lumina_launcher --mode sim|paper`` — daemon full supervisor loop
  - ``python -m lumina_launcher --headless`` — continuous 24/7 production headless runtime
  - ``python -m lumina_launcher --smoke`` — one-shot HeadlessRuntime (CI/smoke)
  - ``python -m lumina_launcher birth status`` — Birth Phase status reporting
  - Neural Command Deck: ``cd tauri-app && npm run tauri dev`` with FastAPI backend on :8000
"""
