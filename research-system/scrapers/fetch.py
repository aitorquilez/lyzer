"""
scrapers/fetch.py — Web Fetcher Module

Descarga páginas web, extrae texto limpio con BeautifulSoup,
mantiene cache en SQLite y soporta fetch asíncrono con aiohttp.
"""

import asyncio
import hashlib
import logging
import random
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp
import requests
from bs4 import BeautifulSoup

from config import (
    CACHE_DIR,
    MAX_CONTENT_CHARS,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENTS,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Cache SQLite
# ──────────────────────────────────────────────────────────────────────────────

class _SQLiteCache:
    """Cache liviano usando SQLite. Thread-safe para reads; writes usan WAL."""

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    url_hash TEXT PRIMARY KEY,
                    url      TEXT NOT NULL,
                    title    TEXT,
                    content  TEXT,
                    fetched_at REAL
                )
                """
            )
            con.commit()

    def get(self, url: str) -> Optional[dict]:
        key = hashlib.sha256(url.encode()).hexdigest()
        with closing(sqlite3.connect(self.db_path)) as con:
            row = con.execute(
                "SELECT url, title, content, fetched_at FROM cache WHERE url_hash=?",
                (key,),
            ).fetchone()
        if row:
            return {"url": row[0], "title": row[1], "content": row[2],
                    "fetched_at": row[3], "cached": True, "status": 200}
        return None

    def set(self, url: str, title: str, content: str):
        key = hashlib.sha256(url.encode()).hexdigest()
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute(
                """
                INSERT OR REPLACE INTO cache (url_hash, url, title, content, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, url, title, content, time.time()),
            )
            con.commit()

    def clear(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DELETE FROM cache")
            con.commit()


# ──────────────────────────────────────────────────────────────────────────────
# HTML → texto limpio
# ──────────────────────────────────────────────────────────────────────────────

_NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside",
               "noscript", "iframe", "form", "button", "svg", "img"]

def _extract_text(html: str) -> tuple[str, str]:
    """
    Convierte HTML a (title, texto_limpio).
    Elimina tags de ruido y normaliza whitespace.
    """
    soup = BeautifulSoup(html, "lxml")

    # Título
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Elimina tags de ruido
    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    # Prioriza main content si existe
    main = soup.find("main") or soup.find("article") or soup.find("body") or soup

    # Texto
    text = main.get_text(separator="\n", strip=True)

    # Normaliza líneas vacías múltiples → máximo 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text


# ──────────────────────────────────────────────────────────────────────────────
# WebFetcher
# ──────────────────────────────────────────────────────────────────────────────

class WebFetcher:
    """
    Descarga URLs y extrae texto limpio.

    - Cache SQLite automático (skip re-fetch).
    - Rotación de User-Agent.
    - Rate limiting configurable.
    - fetch_multiple: modo sync (simple) o async (rápido).
    """

    def __init__(
        self,
        timeout:   int   = REQUEST_TIMEOUT,
        delay:     float = REQUEST_DELAY,
        max_chars: int   = MAX_CONTENT_CHARS,
        cache_dir: Path  = CACHE_DIR,
    ):
        self.timeout   = timeout
        self.delay     = delay
        self.max_chars = max_chars
        self.cache     = _SQLiteCache(cache_dir / "fetch_cache.db")

        self.session = requests.Session()
        self._rotate_agent()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rotate_agent(self):
        self.session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    # ── Fetch síncrono ────────────────────────────────────────────────────────

    def fetch(self, url: str) -> dict:
        """
        Descarga una URL y retorna contenido limpio.

        Returns:
            dict con keys: url, title, content, status, cached, error (si falla)
        """
        if not self._is_valid_url(url):
            return {"url": url, "status": 0, "error": "URL inválida", "content": None}

        # Check cache
        cached = self.cache.get(url)
        if cached:
            logger.debug(f"Cache hit: {url}")
            cached["content"] = cached["content"][: self.max_chars]
            return cached

        self._rotate_agent()
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return {"url": url, "status": resp.status_code,
                        "error": f"Content-Type no soportado: {content_type}",
                        "content": None}

            title, text = _extract_text(resp.text)
            content = text[: self.max_chars]

            self.cache.set(url, title, content)

            return {
                "url":     url,
                "title":   title,
                "content": content,
                "status":  resp.status_code,
                "cached":  False,
            }

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout: {url}")
            return {"url": url, "status": 408, "error": "Timeout", "content": None}
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"ConnectionError: {url} → {e}")
            return {"url": url, "status": 0, "error": "Connection error", "content": None}
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTPError: {url} → {e}")
            return {"url": url, "status": e.response.status_code,
                    "error": str(e), "content": None}
        except Exception as e:
            logger.error(f"Error inesperado: {url} → {e}")
            return {"url": url, "status": 500, "error": str(e), "content": None}

    # ── Fetch múltiple síncrono ───────────────────────────────────────────────

    def fetch_multiple(self, urls: list[str]) -> list[dict]:
        """
        Descarga múltiples URLs de forma secuencial con rate limiting.
        Más lento pero más seguro frente a bloqueos.
        """
        results = []
        for i, url in enumerate(urls):
            logger.info(f"[{i+1}/{len(urls)}] Fetching: {url}")
            result = self.fetch(url)
            results.append(result)
            if not result.get("cached"):
                time.sleep(self.delay)
        return results

    # ── Fetch múltiple asíncrono ──────────────────────────────────────────────

    async def _fetch_async_one(
        self,
        session: "aiohttp.ClientSession",
        url: str,
    ) -> dict:
        """Fetch asíncrono de una URL."""
        # Check cache primero (sync, rápido)
        cached = self.cache.get(url)
        if cached:
            cached["content"] = cached["content"][: self.max_chars]
            return cached

        headers = {"User-Agent": random.choice(USER_AGENTS)}
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=headers,
                allow_redirects=True,
                ssl=False,
            ) as resp:
                if resp.status >= 400:
                    return {"url": url, "status": resp.status,
                            "error": f"HTTP {resp.status}", "content": None}

                html = await resp.text(errors="replace")
                title, text = _extract_text(html)
                content = text[: self.max_chars]
                self.cache.set(url, title, content)

                return {
                    "url":     url,
                    "title":   title,
                    "content": content,
                    "status":  resp.status,
                    "cached":  False,
                }

        except asyncio.TimeoutError:
            return {"url": url, "status": 408, "error": "Timeout", "content": None}
        except Exception as e:
            return {"url": url, "status": 500, "error": str(e), "content": None}

    async def _fetch_all_async(self, urls: list[str]) -> list[dict]:
        """Descarga todas las URLs concurrentemente."""
        connector = aiohttp.TCPConnector(limit=8, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self._fetch_async_one(session, url) for url in urls]
            return await asyncio.gather(*tasks)

    def fetch_multiple_async(self, urls: list[str]) -> list[dict]:
        """
        Descarga múltiples URLs en paralelo usando asyncio + aiohttp.
        Más rápido que fetch_multiple() pero puede triggear rate limits.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # En contextos donde ya hay un loop (Jupyter, etc.)
                import nest_asyncio
                nest_asyncio.apply()
            return loop.run_until_complete(self._fetch_all_async(urls))
        except RuntimeError:
            return asyncio.run(self._fetch_all_async(urls))
