"""
scrapers/search.py — Web Search Module

Busca información usando DuckDuckGo con soporte para múltiples queries
en paralelo, priorización de URLs y rate limiting.
"""

import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from duckduckgo_search import DDGS

from config import SEARCH_REGION, SEARCH_MAX_RESULTS, SEARCH_DELAY

logger = logging.getLogger(__name__)


class WebSearcher:
    """
    Wrapper sobre duckduckgo-search con:
    - Rate limiting automático
    - Múltiples queries en paralelo (threads)
    - Deduplicación por URL
    - Priorización de resultados por patrones
    """

    def __init__(
        self,
        region: str = SEARCH_REGION,
        timeout: int = 30,
        delay: float = SEARCH_DELAY,
    ):
        self.region  = region
        self.timeout = timeout
        self.delay   = delay
        # DDGS se instancia por llamada para evitar problemas de concurrencia
        self._all_results: list[dict] = []

    # ──────────────────────────────────────────────────────────────────────────
    # Búsqueda individual
    # ──────────────────────────────────────────────────────────────────────────

    def search(self, query: str, max_results: int = SEARCH_MAX_RESULTS) -> list[dict]:
        """
        Ejecuta una query en DuckDuckGo.

        Returns:
            list[dict] con keys: title, url, snippet, source, query, timestamp
        """
        logger.info(f"Buscando: {query!r}")
        try:
            with DDGS(timeout=self.timeout) as ddgs:
                raw = ddgs.text(
                    keywords=query,
                    region=self.region,
                    max_results=max_results,
                )

            parsed = [
                {
                    "title":     r.get("title", ""),
                    "url":       r.get("href", ""),
                    "snippet":   r.get("body", ""),
                    "source":    "DuckDuckGo",
                    "query":     query,
                    "timestamp": time.time(),
                }
                for r in raw
                if r.get("href")
            ]
            logger.debug(f"  → {len(parsed)} resultados para: {query!r}")
            return parsed

        except Exception as exc:
            logger.error(f"Search error para {query!r}: {exc}")
            return []

    # ──────────────────────────────────────────────────────────────────────────
    # Múltiples queries
    # ──────────────────────────────────────────────────────────────────────────

    def multi_search(
        self,
        queries: list[str],
        max_results: int = SEARCH_MAX_RESULTS,
        parallel: bool = False,
        max_workers: int = 3,
    ) -> list[dict]:
        """
        Ejecuta múltiples queries y consolida los resultados.

        Args:
            queries:     Lista de strings de búsqueda.
            max_results: Resultados máximos por query.
            parallel:    Si True, usa ThreadPoolExecutor (más rápido, pero
                         DuckDuckGo puede rate-limitarte si abusas).
            max_workers: Hilos simultáneos cuando parallel=True.

        Returns:
            Lista deduplicada por URL, en orden de aparición.
        """
        all_results: list[dict] = []
        seen_urls: set[str]     = set()

        if parallel:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(self.search, q, max_results): q
                    for q in queries
                }
                for future in as_completed(futures):
                    for item in future.result():
                        if item["url"] not in seen_urls:
                            seen_urls.add(item["url"])
                            all_results.append(item)
        else:
            for query in queries:
                for item in self.search(query, max_results):
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        all_results.append(item)
                time.sleep(self.delay)

        self._all_results.extend(all_results)
        logger.info(f"Total resultados únicos: {len(all_results)}")
        return all_results

    # ──────────────────────────────────────────────────────────────────────────
    # Priorización
    # ──────────────────────────────────────────────────────────────────────────

    def prioritize_urls(
        self,
        results: list[dict],
        priority_patterns: list[str],
    ) -> list[dict]:
        """
        Reordena resultados para que los que coincidan con priority_patterns
        aparezcan primero (en el orden en que aparecen en priority_patterns).

        Args:
            results:           Resultados de búsqueda.
            priority_patterns: Substrings de URLs a priorizar.
                               Ej: ["mai-cdmo.com", "linkedin.com", "datoscif.es"]

        Returns:
            Lista reordenada. Las URLs sin match van al final.
        """
        tiers: dict[int, list[dict]] = {i: [] for i in range(len(priority_patterns))}
        rest: list[dict] = []

        for item in results:
            url = item.get("url", "")
            matched = False
            for idx, pattern in enumerate(priority_patterns):
                if pattern.lower() in url.lower():
                    tiers[idx].append(item)
                    matched = True
                    break
            if not matched:
                rest.append(item)

        prioritized: list[dict] = []
        for idx in range(len(priority_patterns)):
            prioritized.extend(tiers[idx])
        prioritized.extend(rest)

        return prioritized

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def get_unique_urls(self, results: Optional[list[dict]] = None) -> list[str]:
        """Devuelve lista de URLs únicas de los resultados."""
        source = results if results is not None else self._all_results
        seen:  set[str]  = set()
        urls:  list[str] = []
        for item in source:
            url = item.get("url", "")
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return urls
