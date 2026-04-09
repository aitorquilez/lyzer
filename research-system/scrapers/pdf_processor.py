"""
scrapers/pdf_processor.py — PDF Processor Module

Extrae texto, tablas y metadata de archivos PDF usando pdfplumber.
Soporta extracción por secciones y límite de páginas.
"""

import logging
import re
from pathlib import Path
from typing import Optional

import pdfplumber

from config import PDF_MAX_PAGES

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Procesa PDFs y extrae:
    - Texto completo (página a página)
    - Tablas estructuradas
    - Metadata del documento
    - Secciones identificadas por encabezados
    """

    def __init__(self, max_pages: int = PDF_MAX_PAGES):
        self.max_pages = max_pages

    # ── Extracción de texto ───────────────────────────────────────────────────

    def extract_text(self, pdf_path: str | Path) -> dict:
        """
        Extrae texto completo del PDF.

        Returns:
            dict con keys: text, pages, metadata, error (si falla)
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {"error": f"Archivo no encontrado: {pdf_path}"}

        logger.info(f"Procesando PDF: {pdf_path.name}")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text: list[str] = []
                n_pages = min(len(pdf.pages), self.max_pages)

                for i, page in enumerate(pdf.pages[:n_pages]):
                    text = page.extract_text() or ""
                    pages_text.append(text)
                    logger.debug(f"  Página {i+1}/{n_pages}: {len(text)} chars")

                full_text = "\n\n".join(pages_text)
                metadata  = dict(pdf.metadata) if pdf.metadata else {}

                return {
                    "text":     full_text,
                    "pages":    n_pages,
                    "metadata": metadata,
                }

        except Exception as exc:
            logger.error(f"Error procesando {pdf_path}: {exc}")
            return {"error": str(exc), "text": "", "pages": 0}

    # ── Extracción de tablas ──────────────────────────────────────────────────

    def extract_tables(self, pdf_path: str | Path) -> list[dict]:
        """
        Extrae todas las tablas del PDF.

        Returns:
            list[dict] con keys: page, data (list[list[str]])
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return []

        tables: list[dict] = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages[: self.max_pages]):
                    page_tables = page.extract_tables()
                    for table in page_tables:
                        # Limpia celdas None
                        clean = [
                            [cell or "" for cell in row]
                            for row in table
                        ]
                        tables.append({"page": i + 1, "data": clean})

        except Exception as exc:
            logger.error(f"Error extrayendo tablas: {exc}")

        logger.info(f"Tablas encontradas: {len(tables)}")
        return tables

    # ── Extracción estructurada por secciones ─────────────────────────────────

    def extract_sections(
        self,
        pdf_path: str | Path,
        section_names: Optional[list[str]] = None,
        chars_per_section: int = 1500,
    ) -> dict:
        """
        Divide el texto del PDF en secciones por encabezados.

        Args:
            pdf_path:          Ruta al PDF.
            section_names:     Lista de encabezados a buscar.
                               Si es None, detecta automáticamente.
            chars_per_section: Máximo de chars por sección.

        Returns:
            dict {section_name: text}
        """
        result = self.extract_text(pdf_path)
        text   = result.get("text", "")

        if not text:
            return {}

        if section_names:
            return self._extract_named_sections(text, section_names, chars_per_section)
        else:
            return self._auto_detect_sections(text, chars_per_section)

    def _extract_named_sections(
        self,
        text: str,
        names: list[str],
        max_chars: int,
    ) -> dict:
        """Extrae secciones específicas buscando los nombres en el texto."""
        sections: dict[str, str] = {}
        text_lower = text.lower()

        for name in names:
            idx = text_lower.find(name.lower())
            if idx == -1:
                continue

            # Busca el inicio de la siguiente sección para delimitar
            next_idx = len(text)
            for other in names:
                if other == name:
                    continue
                oi = text_lower.find(other.lower(), idx + len(name))
                if oi != -1 and oi < next_idx:
                    next_idx = oi

            snippet = text[idx: idx + max_chars]
            sections[name] = snippet.strip()

        return sections

    def _auto_detect_sections(self, text: str, max_chars: int) -> dict:
        """
        Detecta secciones automáticamente buscando líneas cortas en mayúsculas
        o seguidas de salto de línea (heurística para slides/decks).
        """
        # Patrón: línea corta (<= 50 chars) que parece un título
        title_pattern = re.compile(
            r"(?m)^([A-Z][A-Z\s&/\-]{2,48}[A-Z])$"
        )
        matches = list(title_pattern.finditer(text))

        if not matches:
            return {"full_text": text[:max_chars]}

        sections: dict[str, str] = {}
        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start = match.end()
            end   = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body  = text[start:end].strip()[:max_chars]
            sections[title] = body

        return sections

    # ── Full extract (texto + tablas + metadata) ──────────────────────────────

    def extract_all(self, pdf_path: str | Path) -> dict:
        """
        Extrae todo de una vez: texto, tablas y metadata.

        Returns:
            dict con keys: text, pages, metadata, tables
        """
        text_result = self.extract_text(pdf_path)
        tables      = self.extract_tables(pdf_path)
        return {**text_result, "tables": tables}
