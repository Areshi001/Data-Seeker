from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

APP_NAME = "Data Seeker"
DEFAULT_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///amazon.db")
DEFAULT_OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_SQL_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-v4-flash")
DEFAULT_ANALYST_MODEL = os.getenv("OPENROUTER_ANALYST_MODEL", "google/gemma-4-31b-it:free")
