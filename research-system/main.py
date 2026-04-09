"""
main.py — Main Orchestrator + CLI

Ejecuta el flujo completo:
  search → fetch → (pdf) → analyze → (llm synthesis) → report

Uso CLI:
    python main.py "Mai CDMO" --website mai-cdmo.com --pdf deck.pdf
    python main.py "Ferrovial" --region es-es --async-fetch

Uso programático:
    from main import run
    result = run("Mai CDMO", website="mai-cdmo.com", pdf_path="deck.pdf")
"""

import json
import logging
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import click

from config import (
    ANTHROPIC_API_KEY,
    LOG_FORMAT,
    LOG_LEVEL,
    MAX_URLS_TO_FETCH,
    OUTPUT_DIR,
    SEARCH_MAX_RESULTS,
)
from llm.synthesis import LLMSynthesizer
from processors.analyzer import DataAnalyzer
from processors.report_generator import ReportGenerator
from scrapers.fetch import WebFetcher
from scrapers.pdf_processor import PDFProcessor
from scrapers.search import WebSearcher

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger("research")


# ──────────────────────────────────────────────────────────────────────────────
# ResearchSystem
# ──────────────────────────────────────────────────────────────────────────────

class ResearchSystem:
    """
    Orquestador principal del sistema de investigación.

    Flujo:
        1. Web Search   → queries DuckDuckGo
        2. Prioritize   → ordena URLs por relevancia
        3. Web Fetch    → descarga y extrae texto
        4. PDF Process  → extrae texto/tablas del PDF (opcional)
        5. Analyze      → extrae entidades y consolida
        6. LLM Synth    → Claude genera resumen ejecutivo (si hay API key)
        7. Report       → genera .md + .html + .json

    Args:
        region:           Región DuckDuckGo (ej: "es-es").
        async_fetch:      Usa aiohttp paralelo para descargas.
        anthropic_key:    API key de Anthropic (override del .env).
        progress_callback: Función que recibe mensajes de progreso (str).
                           Si es None, usa print().
    """

    def __init__(
        self,
        region: str = "es-es",
        async_fetch: bool = False,
        anthropic_key: str = "",
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.searcher      = WebSearcher(region=region)
        self.fetcher       = WebFetcher()
        self.pdf_processor = PDFProcessor()
        self.analyzer      = DataAnalyzer()
        self.report_gen    = ReportGenerator()
        self.llm           = LLMSynthesizer(api_key=anthropic_key or ANTHROPIC_API_KEY)
        self.async_fetch   = async_fetch
        self._emit         = progress_callback or print

    # ── Research principal ────────────────────────────────────────────────────

    def research(
        self,
        company_name: str,
        website:      Optional[str] = None,
        queries:      Optional[list[str]] = None,
        pdf_path:     Optional[str | Path] = None,
        max_urls:     int = MAX_URLS_TO_FETCH,
        export_html:  bool = True,
    ) -> dict:
        """
        Ejecuta la investigación completa.

        Args:
            company_name: Nombre de la empresa a investigar.
            website:      Dominio principal (ej: "mai-cdmo.com").
            queries:      Queries adicionales. Si None, se generan automáticamente.
            pdf_path:     Ruta a un PDF adicional (deck, informe, etc.).
            max_urls:     Máximo de URLs a descargar.
            export_html:  Si True, genera también reporte HTML.

        Returns:
            dict con todos los datos consolidados.
        """
        t_start = time.time()
        emit    = self._emit

        emit(f"{'='*55}")
        emit(f"RESEARCH: {company_name}")
        emit(f"{'='*55}")

        # ── PASO 1: Búsqueda ──────────────────────────────────────────────────
        emit("[1/6] Buscando en la web...")
        all_queries = self._build_queries(company_name, website, queries)
        emit(f"      {len(all_queries)} queries preparadas")

        search_results = self.searcher.multi_search(
            all_queries,
            max_results=SEARCH_MAX_RESULTS,
            parallel=False,
        )
        emit(f"      ✓ {len(search_results)} resultados encontrados")

        # ── PASO 2: Priorizar URLs ────────────────────────────────────────────
        priority_patterns = self._build_priority_patterns(website)
        prioritized       = self.searcher.prioritize_urls(search_results, priority_patterns)
        urls_to_fetch     = self.searcher.get_unique_urls(prioritized)[:max_urls]
        emit(f"      ✓ {len(urls_to_fetch)} URLs seleccionadas")

        # ── PASO 3: Fetch ─────────────────────────────────────────────────────
        emit(f"[2/6] Descargando páginas {'(async)' if self.async_fetch else ''}...")
        if self.async_fetch:
            fetch_results = self.fetcher.fetch_multiple_async(urls_to_fetch)
        else:
            fetch_results = self.fetcher.fetch_multiple(urls_to_fetch)

        ok  = sum(1 for r in fetch_results if r.get("content"))
        err = len(fetch_results) - ok
        emit(f"      ✓ {ok} páginas ok, {err} errores")

        # ── PASO 4: PDF ───────────────────────────────────────────────────────
        pdf_content: Optional[str] = None
        if pdf_path:
            emit(f"[3/6] Procesando PDF: {Path(pdf_path).name}")
            pdf_data    = self.pdf_processor.extract_all(pdf_path)
            pdf_content = pdf_data.get("text", "")
            n_tables    = len(pdf_data.get("tables", []))
            emit(f"      ✓ {pdf_data.get('pages', 0)} páginas, {n_tables} tablas")
        else:
            emit("[3/6] PDF: (ninguno proporcionado)")

        # ── PASO 5: Análisis ──────────────────────────────────────────────────
        emit("[4/6] Analizando y consolidando datos...")
        raw_texts  = self._build_raw_texts(fetch_results, pdf_content)
        sources    = {k: v for k, v in raw_texts.items()}
        consolidated = self.analyzer.consolidate(sources)

        n_people   = len(consolidated.get("aggregated", {}).get("people", []))
        n_fin      = sum(1 for v in consolidated.get("financial", {}).values() if v)
        n_contra   = len(consolidated.get("contradictions", []))
        emit(f"      ✓ {len(sources)} fuentes | {n_people} personas | {n_fin} métricas financieras")
        if n_contra:
            emit(f"      ⚠ {n_contra} contradicción(es) detectada(s)")

        # Enriquece con metadata de sesión
        consolidated["search_results_count"] = len(search_results)
        consolidated["urls_fetched"]          = urls_to_fetch
        consolidated["queries_used"]          = all_queries

        # ── PASO 6: Síntesis LLM ─────────────────────────────────────────────
        llm_summary = ""
        if self.llm.enabled:
            emit("[5/6] Sintetizando con Claude...")
            llm_summary = self.llm.synthesize(company_name, consolidated, raw_texts)
            emit("      ✓ Síntesis completada")
            consolidated["llm_summary"] = llm_summary
        else:
            emit("[5/6] Síntesis LLM: (sin API key — saltando)")
            consolidated["llm_summary"] = ""

        # ── PASO 7: Reporte ───────────────────────────────────────────────────
        emit("[6/6] Generando reportes...")
        output_paths = self.report_gen.generate(
            data         = consolidated,
            company_name = company_name,
            export_html  = export_html,
        )

        # JSON
        slug      = company_name.lower().replace(" ", "_")
        json_path = OUTPUT_DIR / f"{slug}_data.json"
        json_path.write_text(
            self.analyzer.to_json(consolidated), encoding="utf-8"
        )

        elapsed = time.time() - t_start
        emit(f"{'='*55}")
        emit(f"COMPLETADO en {elapsed:.1f}s")
        emit(f"MD:   {output_paths['md']}")
        if output_paths.get("html"):
            emit(f"HTML: {output_paths['html']}")
        emit(f"JSON: {json_path}")
        emit(f"{'='*55}")

        # Guarda paths para el caller
        consolidated["_output_paths"] = {
            "md":   str(output_paths["md"]),
            "html": str(output_paths.get("html", "")),
            "json": str(json_path),
        }

        return consolidated

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _build_queries(
        company_name: str,
        website: Optional[str],
        extra_queries: Optional[list[str]],
    ) -> list[str]:
        base = [
            f'"{company_name}" empresa',
            f'"{company_name}" CEO founder equipo directivo',
            f'"{company_name}" financiación inversión ronda',
            f'"{company_name}" revenue ingresos facturación',
        ]
        if website:
            base.insert(0, f"site:{website}")
        if extra_queries:
            base.extend(extra_queries)
        return base

    @staticmethod
    def _build_priority_patterns(website: Optional[str]) -> list[str]:
        patterns = []
        if website:
            patterns.append(website)
        patterns.extend([
            "linkedin.com",
            "crunchbase.com",
            "datoscif.es",
            "informa.es",
            "boe.es",
        ])
        return patterns

    @staticmethod
    def _build_raw_texts(
        fetch_results: list[dict],
        pdf_content: Optional[str],
    ) -> dict[str, str]:
        texts: dict[str, str] = {}
        for i, result in enumerate(fetch_results):
            content = result.get("content")
            if not content:
                continue
            url = result.get("url", f"source_{i}")
            try:
                domain = urlparse(url).netloc.replace("www.", "")
            except Exception:
                domain = f"source_{i}"
            texts[domain] = content
        if pdf_content:
            texts["pdf"] = pdf_content
        return texts


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

@click.command()
@click.argument("company_name")
@click.option("--website",    "-w", default=None,  help="Dominio principal (ej: mai-cdmo.com)")
@click.option("--pdf",        "-p", default=None,  help="Ruta al PDF")
@click.option("--query",      "-q", multiple=True, help="Queries adicionales (repetible)")
@click.option("--max-urls",   default=MAX_URLS_TO_FETCH, show_default=True)
@click.option("--region",     default="es-es", show_default=True)
@click.option("--async-fetch", is_flag=True, default=False, help="Fetch paralelo con aiohttp")
@click.option("--no-html",    is_flag=True, default=False,  help="No genera HTML")
@click.option("--verbose",    "-v", is_flag=True, default=False)
def cli(company_name, website, pdf, query, max_urls, region, async_fetch, no_html, verbose):
    """
    Sistema de investigación web automático.

    \b
    Ejemplos:
      python main.py "Mai CDMO" --website mai-cdmo.com
      python main.py "Mai CDMO" --website mai-cdmo.com --pdf deck.pdf
      python main.py "Ferrovial" --region es-es --max-urls 20 --async-fetch
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    system = ResearchSystem(
        region=region,
        async_fetch=async_fetch,
        progress_callback=click.echo,
    )
    system.research(
        company_name = company_name,
        website      = website,
        queries      = list(query) if query else None,
        pdf_path     = pdf,
        max_urls     = max_urls,
        export_html  = not no_html,
    )


# ──────────────────────────────────────────────────────────────────────────────
# API programática
# ──────────────────────────────────────────────────────────────────────────────

def run(
    company_name:  str,
    website:       Optional[str] = None,
    pdf_path:      Optional[str] = None,
    queries:       Optional[list[str]] = None,
    async_fetch:   bool = False,
    region:        str = "es-es",
    anthropic_key: str = "",
    progress_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Punto de entrada programático (sin CLI).

    Ejemplo:
        from main import run
        result = run("Mai CDMO", website="mai-cdmo.com", pdf_path="deck.pdf")
    """
    system = ResearchSystem(
        region=region,
        async_fetch=async_fetch,
        anthropic_key=anthropic_key,
        progress_callback=progress_callback,
    )
    return system.research(
        company_name = company_name,
        website      = website,
        queries      = queries,
        pdf_path     = pdf_path,
    )


if __name__ == "__main__":
    cli()
