"""
llm/synthesis.py — LLM Synthesis Module (Anthropic Claude)

Usa Claude para generar un resumen ejecutivo de la investigación a partir
de los datos extraídos y el texto crudo de las fuentes.
Solo activo si ANTHROPIC_API_KEY está configurado.
"""

import logging
import json
from typing import Any, Optional

from config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """Eres un analista de inversiones y due diligence experto.
Tu tarea es sintetizar información de múltiples fuentes web sobre una empresa
y generar un análisis conciso, objetivo y estructurado en español.

Reglas:
- Sé factual: solo incluye lo que encuentres en los datos.
- Si algo es incierto, indícalo con "según fuentes" o "aparentemente".
- Usa un tono profesional y directo.
- Detecta inconsistencias y las menciona.
- Máximo 500 palabras en el resumen ejecutivo."""


_USER_TEMPLATE = """Empresa: {company_name}

## Datos extraídos automáticamente:

### Métricas financieras:
{financial_json}

### Entidades detectadas:
- Personas/equipo: {people}
- Emails: {emails}
- CIF/NIF: {cif}
- Años mencionados: {years}
- Valores monetarios: {money}

### Contradicciones entre fuentes:
{contradictions}

### Extractos de texto de fuentes ({n_sources} fuentes):
{text_snippets}

---
Por favor genera:
1. **Resumen ejecutivo** (3-4 párrafos): qué hace la empresa, quién la dirige, situación financiera, valoración.
2. **Puntos clave** (bullet points): los 5-7 datos más relevantes para un inversor.
3. **Señales de alerta** (si las hay): inconsistencias, datos que no cuadran, info que falta.
4. **Próximos pasos recomendados**: qué validar manualmente.
"""


class LLMSynthesizer:
    """
    Wrapper de Anthropic Claude para síntesis de investigación.
    Si no hay API key configurada, devuelve texto vacío sin fallar.
    """

    def __init__(self, api_key: str = ANTHROPIC_API_KEY, model: str = ANTHROPIC_MODEL):
        self.model   = model
        self.enabled = bool(api_key)
        self._client = None

        if self.enabled:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
                logger.info(f"LLM synthesis activado: {model}")
            except ImportError:
                logger.warning("anthropic no instalado. pip install anthropic")
                self.enabled = False
            except Exception as e:
                logger.error(f"Error inicializando Anthropic: {e}")
                self.enabled = False
        else:
            logger.info("ANTHROPIC_API_KEY no configurada — síntesis LLM desactivada")

    # ── Síntesis principal ────────────────────────────────────────────────────

    def synthesize(
        self,
        company_name: str,
        consolidated: dict[str, Any],
        raw_texts: dict[str, str],
        max_snippet_chars: int = 800,
        model: Optional[str] = None,
    ) -> str:
        """
        Genera un análisis ejecutivo usando Claude.

        Args:
            company_name:  Nombre de la empresa.
            consolidated:  Salida de DataAnalyzer.consolidate().
            raw_texts:     dict {fuente: texto_crudo} de las páginas descargadas.
            max_snippet_chars: Chars máximos por snippet de texto.

        Returns:
            Texto Markdown con el análisis, o "" si LLM está desactivado.
        """
        if not self.enabled:
            return ""

        agg          = consolidated.get("aggregated", {})
        financial    = consolidated.get("financial", {})
        contradictions = consolidated.get("contradictions", [])

        # Prepara snippets de texto (limita tamaño total)
        snippets: list[str] = []
        total_chars = 0
        max_total   = 6_000

        for source, text in raw_texts.items():
            if total_chars >= max_total:
                break
            snippet = f"[{source}]\n{text[:max_snippet_chars]}"
            snippets.append(snippet)
            total_chars += len(snippet)

        user_msg = _USER_TEMPLATE.format(
            company_name   = company_name,
            financial_json = json.dumps(financial, ensure_ascii=False, indent=2),
            people         = ", ".join(agg.get("people", [])[:10]) or "—",
            emails         = ", ".join(agg.get("emails", [])) or "—",
            cif            = ", ".join(agg.get("cif", [])) or "—",
            years          = ", ".join(agg.get("years", [])[:10]) or "—",
            money          = ", ".join(agg.get("money", [])[:10]) or "—",
            contradictions = json.dumps(contradictions, ensure_ascii=False, indent=2) if contradictions else "Ninguna",
            n_sources      = len(raw_texts),
            text_snippets  = "\n\n---\n\n".join(snippets) or "Sin texto disponible",
        )

        try:
            use_model = model or self.model
            logger.info(f"Llamando a Claude para síntesis ({use_model})...")
            message = self._client.messages.create(
                model      = use_model,
                max_tokens = 1024,
                system     = _SYSTEM_PROMPT,
                messages   = [{"role": "user", "content": user_msg}],
            )
            result = message.content[0].text
            logger.info(f"Síntesis completada: {len(result)} chars")
            return result

        except Exception as e:
            logger.error(f"Error en síntesis LLM: {e}")
            return f"> ⚠️ Error en síntesis LLM: {e}"

    # ── Chat interactivo (para el frontend) ───────────────────────────────────

    def chat(
        self,
        question: str,
        company_name: str,
        consolidated: dict[str, Any],
        conversation_history: Optional[list[dict]] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        Responde preguntas sobre la investigación en modo conversacional.

        Args:
            question:             Pregunta del usuario.
            company_name:         Nombre de la empresa de contexto.
            consolidated:         Datos del análisis.
            conversation_history: Historial previo [{role, content}, ...].

        Returns:
            Respuesta de Claude como string.
        """
        if not self.enabled:
            return "⚠️ Configura ANTHROPIC_API_KEY en el archivo .env para usar el chat."

        system = (
            f"Eres un analista experto en due diligence. Tienes acceso a los datos "
            f"de investigación sobre '{company_name}'. Responde en español de forma "
            f"concisa y profesional. Solo afirma lo que encuentres en los datos.\n\n"
            f"Datos disponibles:\n"
            f"{json.dumps(consolidated.get('financial', {}), ensure_ascii=False, indent=2)}\n"
            f"Personas: {', '.join(consolidated.get('aggregated', {}).get('people', [])[:15])}\n"
            f"Emails: {', '.join(consolidated.get('aggregated', {}).get('emails', []))}"
        )

        messages = list(conversation_history or [])
        messages.append({"role": "user", "content": question})

        try:
            response = self._client.messages.create(
                model      = model or self.model,
                max_tokens = 512,
                system     = system,
                messages   = messages,
            )
            return response.content[0].text

        except Exception as e:
            logger.error(f"Error en chat LLM: {e}")
            return f"Error: {e}"
