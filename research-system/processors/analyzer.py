"""
processors/analyzer.py — Data Analyzer Module

Extrae entidades estructuradas (números, dinero, fechas, personas, emails,
URLs, métricas financieras) de texto plano y consolida datos de múltiples
fuentes detectando contradicciones.
"""

import json
import logging
import re
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Patrones regex
# ──────────────────────────────────────────────────────────────────────────────

_RE = {
    # Dinero: €1.000, €300K, $5M, 1,5M€
    "money": re.compile(
        r"(?:€|\$|USD|EUR)\s*([\d][0-9.,]*(?:[KMBkmb])?)"
        r"|"
        r"([\d][0-9.,]*(?:[KMBkmb])?)\s*(?:€|EUR|USD|\$)",
        re.IGNORECASE,
    ),
    # Porcentajes
    "percentages": re.compile(r"(\d+(?:[.,]\d+)?)\s*%"),
    # Años
    "years": re.compile(r"\b((?:19|20)\d{2})\b"),
    # Emails
    "emails": re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"),
    # URLs
    "urls": re.compile(r"https?://[^\s<>\"']+"),
    # Fechas DD/MM/YYYY o YYYY-MM-DD
    "dates": re.compile(
        r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b"
        r"|"
        r"\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b"
    ),
    # Personas: dos o más palabras capitalizadas
    "people": re.compile(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)+)\b"),
    # CIF/NIF español
    "cif": re.compile(r"\b([A-Z]\d{7}[A-Z0-9])\b"),
}

# Patrones para métricas financieras (contexto + valor)
_FINANCIAL_PATTERNS: dict[str, re.Pattern] = {
    "revenue":   re.compile(
        r"(?:revenue|ingresos?|ventas?|facturaci[oó]n)[^\d€$]*"
        r"((?:€|\$)?\s*[\d][0-9.,]*(?:[KMBkmb])?(?:\s*(?:€|EUR|USD|\$))?)",
        re.IGNORECASE,
    ),
    "funding":   re.compile(
        r"(?:funding|financiaci[oó]n|inversi[oó]n|ronda)[^\d€$]*"
        r"((?:€|\$)?\s*[\d][0-9.,]*(?:[KMBkmb])?(?:\s*(?:€|EUR|USD|\$))?)",
        re.IGNORECASE,
    ),
    "valuation": re.compile(
        r"(?:valuation|valoraci[oó]n)[^\d€$]*"
        r"((?:€|\$)?\s*[\d][0-9.,]*(?:[KMBkmb])?(?:\s*(?:€|EUR|USD|\$))?)",
        re.IGNORECASE,
    ),
    "cagr":      re.compile(
        r"(?:CAGR|crecimiento\s+anual\s+compuesto)[^\d%]*(\d+(?:[.,]\d+)?)\s*%",
        re.IGNORECASE,
    ),
    "employees": re.compile(
        r"(?:empleados?|employees?|team\s+size|trabajadores?|equipo)[^\d]*(\d+)",
        re.IGNORECASE,
    ),
    "founded":   re.compile(
        r"(?:fundad[ao]|founded|incorporated|constituida?)[^\d]*((?:19|20)\d{2})",
        re.IGNORECASE,
    ),
    "capital":   re.compile(
        r"(?:capital\s+social|share\s+capital)[^\d€$]*"
        r"((?:€|\$)?\s*[\d][0-9.,]*(?:[KMBkmb])?(?:\s*(?:€|EUR|USD|\$))?)",
        re.IGNORECASE,
    ),
}

# Palabras comunes a excluir del listado de "personas"
_PEOPLE_STOPWORDS = {
    "The", "This", "That", "With", "From", "For", "And", "Our", "We",
    "They", "In", "Is", "Are", "Has", "Have", "By", "At", "On", "An",
    "La", "El", "Los", "Las", "De", "Del", "En", "Con", "Por", "Para",
    "Una", "Uno", "Que", "Ser", "Esta", "Este", "Son", "Han", "Sus",
    "Chief", "Executive", "Officer", "Director", "Manager", "Head",
    "Senior", "Junior", "Lead", "General", "Vice", "President",
}


# ──────────────────────────────────────────────────────────────────────────────
# DataAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class DataAnalyzer:
    """
    Extrae entidades estructuradas de texto y consolida múltiples fuentes.
    """

    # ── Extractores individuales ──────────────────────────────────────────────

    def extract_money(self, text: str) -> list[str]:
        matches = _RE["money"].findall(text)
        values  = [m[0] or m[1] for m in matches if m[0] or m[1]]
        return list(dict.fromkeys(values))  # deduplica preservando orden

    def extract_percentages(self, text: str) -> list[str]:
        return list(dict.fromkeys(_RE["percentages"].findall(text)))

    def extract_years(self, text: str) -> list[str]:
        return list(dict.fromkeys(_RE["years"].findall(text)))

    def extract_emails(self, text: str) -> list[str]:
        return list(dict.fromkeys(_RE["emails"].findall(text)))

    def extract_urls(self, text: str) -> list[str]:
        return list(dict.fromkeys(_RE["urls"].findall(text)))

    def extract_dates(self, text: str) -> list[str]:
        raw = _RE["dates"].findall(text)
        # Normaliza tuplas a strings "DD/MM/YYYY" o "YYYY-MM-DD"
        dates: list[str] = []
        for match in raw:
            if match[0]:  # DD/MM/YYYY
                dates.append(f"{match[0]}/{match[1]}/{match[2]}")
            else:         # YYYY-MM-DD
                dates.append(f"{match[3]}-{match[4]}-{match[5]}")
        return list(dict.fromkeys(dates))

    def extract_people(self, text: str) -> list[str]:
        candidates = _RE["people"].findall(text)
        return [
            name for name in dict.fromkeys(candidates)
            if not any(w in name.split() for w in _PEOPLE_STOPWORDS)
            and len(name.split()) >= 2
        ]

    def extract_cif(self, text: str) -> list[str]:
        return list(dict.fromkeys(_RE["cif"].findall(text)))

    def extract_financial_metrics(self, text: str) -> dict[str, str | None]:
        """
        Extrae métricas financieras clave del texto.

        Returns:
            dict {metric_name: first_value_found_or_None}
        """
        metrics: dict[str, str | None] = {}
        for metric, pattern in _FINANCIAL_PATTERNS.items():
            match = pattern.search(text)
            metrics[metric] = match.group(1).strip() if match else None
        return metrics

    def extract_all(self, text: str) -> dict[str, Any]:
        """
        Ejecuta todos los extractores sobre un texto.

        Returns:
            dict con todas las entidades extraídas.
        """
        return {
            "money":      self.extract_money(text),
            "percentages": self.extract_percentages(text),
            "years":      self.extract_years(text),
            "emails":     self.extract_emails(text),
            "urls":       self.extract_urls(text),
            "dates":      self.extract_dates(text),
            "people":     self.extract_people(text),
            "cif":        self.extract_cif(text),
            "financial":  self.extract_financial_metrics(text),
        }

    # ── Consolidación multi-fuente ────────────────────────────────────────────

    def consolidate(self, sources: dict[str, str]) -> dict[str, Any]:
        """
        Consolida datos extraídos de múltiples fuentes.

        Args:
            sources: dict {nombre_fuente: texto_plano}
                     Ej: {"website": "...", "linkedin": "...", "pdf": "..."}

        Returns:
            dict con datos consolidados + análisis de contradicciones.
        """
        per_source: dict[str, dict] = {}
        for name, text in sources.items():
            if not text:
                continue
            per_source[name] = self.extract_all(text)
            logger.debug(f"Fuente '{name}': {len(text)} chars procesados")

        # Agrega entidades simples (unión de listas, deduplicadas)
        aggregated: dict[str, list] = defaultdict(list)
        for name, data in per_source.items():
            for key in ("money", "percentages", "years", "emails",
                        "urls", "dates", "people", "cif"):
                for val in data.get(key, []):
                    if val not in aggregated[key]:
                        aggregated[key].append(val)

        # Consolida métricas financieras + detecta contradicciones
        financial_merged, contradictions = self._merge_financial(per_source)

        return {
            "per_source":     per_source,
            "aggregated":     dict(aggregated),
            "financial":      financial_merged,
            "contradictions": contradictions,
            "sources_count":  len(per_source),
        }

    def _merge_financial(
        self,
        per_source: dict[str, dict],
    ) -> tuple[dict[str, str | None], list[dict]]:
        """
        Agrupa métricas financieras por nombre.
        Si distintas fuentes dan valores distintos para la misma métrica,
        registra la contradicción.

        Returns:
            (merged_metrics, contradictions_list)
        """
        by_metric: dict[str, dict[str, str]] = defaultdict(dict)

        for source, data in per_source.items():
            for metric, value in data.get("financial", {}).items():
                if value:
                    by_metric[metric][source] = value

        merged: dict[str, str | None] = {}
        contradictions: list[dict]    = []

        for metric, source_values in by_metric.items():
            unique_vals = list(dict.fromkeys(source_values.values()))
            if len(unique_vals) == 1:
                merged[metric] = unique_vals[0]
            elif len(unique_vals) > 1:
                # Contradicción: toma el valor de la fuente más fiable
                # (primera en el dict, que ya viene priorizada)
                merged[metric] = unique_vals[0]
                contradictions.append({
                    "metric":     metric,
                    "by_source":  source_values,
                    "chosen":     unique_vals[0],
                })
                logger.warning(
                    f"Contradicción en '{metric}': {source_values}"
                )
            else:
                merged[metric] = None

        # Rellena métricas sin datos
        for metric in _FINANCIAL_PATTERNS:
            merged.setdefault(metric, None)

        return merged, contradictions

    # ── Utils ─────────────────────────────────────────────────────────────────

    def to_json(self, data: dict, indent: int = 2) -> str:
        """Serializa el resultado consolidado a JSON."""
        return json.dumps(data, ensure_ascii=False, indent=indent, default=str)
