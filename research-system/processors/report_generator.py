"""
processors/report_generator.py — Report Generator Module

Genera reportes Markdown estructurados usando Jinja2 y los exporta
opcionalmente a HTML con estilos incorporados.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import markdown2
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import OUTPUT_DIR, TEMPLATE_DIR

logger = logging.getLogger(__name__)

# CSS embebido para el reporte HTML
_HTML_STYLE = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 960px;
    margin: 40px auto;
    padding: 0 20px;
    color: #222;
    line-height: 1.6;
}
h1 { border-bottom: 3px solid #2c7be5; padding-bottom: 8px; }
h2 { color: #2c7be5; margin-top: 2em; }
h3 { color: #444; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; }
th { background: #2c7be5; color: #fff; padding: 8px 12px; text-align: left; }
td { border: 1px solid #ddd; padding: 8px 12px; }
tr:nth-child(even) { background: #f5f7fa; }
code { background: #f0f0f0; padding: 2px 5px; border-radius: 3px; }
pre  { background: #f0f0f0; padding: 1em; border-radius: 4px; overflow-x: auto; }
blockquote { border-left: 4px solid #2c7be5; margin: 0; padding-left: 1em; color: #555; }
.meta { color: #888; font-size: 0.9em; margin-bottom: 2em; }
.warning { background: #fff3cd; border-left: 4px solid #ffc107;
           padding: 0.5em 1em; margin: 1em 0; }
"""


class ReportGenerator:
    """
    Genera reportes Markdown desde plantillas Jinja2 y los convierte a HTML.
    """

    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Filtros de utilidad disponibles en las plantillas
        self.env.filters["default_if_none"] = lambda v, d="N/D": v if v else d
        self.env.filters["join_list"]       = lambda lst, sep=", ": sep.join(lst) if lst else "—"

    # ── Generar Markdown ──────────────────────────────────────────────────────

    def generate_markdown(
        self,
        data: dict[str, Any],
        company_name: str,
        template_name: str = "report.md.jinja2",
        output_dir: Path = OUTPUT_DIR,
    ) -> tuple[str, Path]:
        """
        Renderiza la plantilla Jinja2 y guarda el archivo .md.

        Args:
            data:          Datos del análisis (salida de DataAnalyzer.consolidate).
            company_name:  Nombre de la empresa (usado en el filename).
            template_name: Nombre del archivo de plantilla.
            output_dir:    Directorio de salida.

        Returns:
            (markdown_content, output_path)
        """
        template = self.env.get_template(template_name)

        context = {
            "company_name":  company_name,
            "generated_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "financial":     data.get("financial", {}),
            "aggregated":    data.get("aggregated", {}),
            "per_source":    data.get("per_source", {}),
            "contradictions": data.get("contradictions", []),
            "sources_count": data.get("sources_count", 0),
            # Metadata de la sesión inyectada directamente
            "search_results_count": data.get("search_results_count", 0),
            "urls_fetched":         data.get("urls_fetched", []),
            "queries_used":         data.get("queries_used", []),
        }

        md_content = template.render(**context)

        slug       = company_name.lower().replace(" ", "_")
        out_path   = output_dir / f"{slug}_report.md"
        out_path.write_text(md_content, encoding="utf-8")

        logger.info(f"Reporte Markdown guardado: {out_path}")
        return md_content, out_path

    # ── Exportar HTML ─────────────────────────────────────────────────────────

    def generate_html(
        self,
        md_content: str,
        company_name: str,
        output_dir: Path = OUTPUT_DIR,
    ) -> Path:
        """
        Convierte Markdown a HTML con estilos embebidos.

        Args:
            md_content:   Contenido Markdown.
            company_name: Nombre de la empresa.
            output_dir:   Directorio de salida.

        Returns:
            Path al archivo HTML generado.
        """
        html_body = markdown2.markdown(
            md_content,
            extras=[
                "tables",
                "fenced-code-blocks",
                "header-ids",
                "toc",
                "strike",
                "footnotes",
            ],
        )

        slug     = company_name.lower().replace(" ", "_")
        out_path = output_dir / f"{slug}_report.html"

        html_full = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{company_name} — Research Report</title>
  <style>{_HTML_STYLE}</style>
</head>
<body>
{html_body}
</body>
</html>
"""
        out_path.write_text(html_full, encoding="utf-8")
        logger.info(f"Reporte HTML guardado: {out_path}")
        return out_path

    # ── Combo: genera ambos ───────────────────────────────────────────────────

    def generate(
        self,
        data: dict[str, Any],
        company_name: str,
        output_dir: Path = OUTPUT_DIR,
        export_html: bool = True,
    ) -> dict[str, Path]:
        """
        Genera Markdown y opcionalmente HTML.

        Returns:
            dict {"md": Path, "html": Path | None}
        """
        md_content, md_path = self.generate_markdown(data, company_name, output_dir=output_dir)

        html_path = None
        if export_html:
            html_path = self.generate_html(md_content, company_name, output_dir=output_dir)

        return {"md": md_path, "html": html_path}
