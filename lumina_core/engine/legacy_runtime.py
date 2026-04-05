from __future__ import annotations

import os

from dotenv import load_dotenv

from lumina_core.logging_utils import build_logger

load_dotenv()

LOG_LEVEL = os.getenv("LUMINA_LOG_LEVEL", "INFO").upper()
logger = build_logger("lumina", log_level=LOG_LEVEL, file_path="lumina_full_log.csv")
