"""
config.py — Configuración global del sistema de investigación.
Centraliza paths, timeouts, rate limits y claves API opcionales.
Carga automáticamente .env si existe.
"""

import os
from pathlib import Path

# Carga .env si python-dotenv está instalado (no falla si no lo está)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
CACHE_DIR    = BASE_DIR / "cache"
OUTPUT_DIR   = BASE_DIR / "output"
TEMPLATE_DIR = BASE_DIR / "templates"      # plantillas Jinja2 de reportes
WEB_DIR      = BASE_DIR / "web_templates"  # plantillas Flask

CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── HTTP ─────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT   = int(os.getenv("REQUEST_TIMEOUT", "15"))
REQUEST_DELAY     = float(os.getenv("REQUEST_DELAY", "1.0"))
MAX_CONTENT_CHARS = int(os.getenv("MAX_CONTENT_CHARS", "5000"))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# ─── Search ───────────────────────────────────────────────────────────────────
SEARCH_REGION      = os.getenv("SEARCH_REGION", "es-es")
SEARCH_MAX_RESULTS = int(os.getenv("SEARCH_MAX_RESULTS", "10"))
SEARCH_DELAY       = float(os.getenv("SEARCH_DELAY", "1.5"))

# ─── Analysis ─────────────────────────────────────────────────────────────────
MAX_URLS_TO_FETCH = int(os.getenv("MAX_URLS_TO_FETCH", "12"))
PDF_MAX_PAGES     = int(os.getenv("PDF_MAX_PAGES", "50"))

# ─── LLM ──────────────────────────────────────────────────────────────────────
# Pon tu clave en el archivo .env:  ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")

# Modelos disponibles (id → etiqueta)
ANTHROPIC_MODELS = {
    "claude-sonnet-4-6":        "Sonnet 4.6  — Recomendado",
    "claude-opus-4-6":          "Opus 4.6    — Más potente",
    "claude-haiku-4-5-20251001": "Haiku 4.5   — Más rápido",
}
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ─── Web app ──────────────────────────────────────────────────────────────────
FLASK_HOST   = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT   = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG  = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
