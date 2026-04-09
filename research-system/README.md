# Research AI — Sistema de Investigación Web

Sistema de investigación automática de empresas. Busca en la web, procesa PDFs,
extrae datos estructurados y genera un informe con síntesis de Claude.

---

## Índice

1. [Instalación](#instalación)
2. [Configuración](#configuración)
3. [Arrancar](#arrancar)
4. [Cómo funciona](#cómo-funciona)
5. [Uso — Interfaz web](#uso--interfaz-web)
6. [Uso — CLI](#uso--cli)
7. [Uso — API programática](#uso--api-programática)
8. [Queries actuales](#queries-actuales)
9. [Estructura de archivos](#estructura-de-archivos)
10. [Roadmap / Próximas mejoras](#roadmap--próximas-mejoras)

---

## Instalación

```bash
cd research-system

# Crear entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Instalar dependencias
pip install -r requirements.txt
```

---

## Configuración

Copia el archivo de ejemplo y rellena tu clave de Anthropic:

```bash
cp .env.example .env
```

Edita `.env`:

```env
# Obligatorio para síntesis LLM y chat
ANTHROPIC_API_KEY=sk-ant-...

# Opcional — modelo por defecto (ver opciones más abajo)
ANTHROPIC_MODEL=claude-sonnet-4-6

# Opcional — ajustes de búsqueda
SEARCH_REGION=es-es          # es-es | us-en | uk-en | wt-wt (global)
MAX_URLS_TO_FETCH=12
REQUEST_TIMEOUT=15
```

> La API key también se puede introducir directamente en la interfaz web
> pulsando el botón **🔑 API Key** del header — no hace falta reiniciar.

### Modelos disponibles

| ID | Etiqueta | Cuándo usarlo |
|----|----------|---------------|
| `claude-sonnet-4-6` | Sonnet 4.6 — Recomendado | Uso general, balance velocidad/calidad |
| `claude-opus-4-6` | Opus 4.6 — Más potente | Análisis complejos, máxima calidad |
| `claude-haiku-4-5-20251001` | Haiku 4.5 — Más rápido | Pruebas rápidas, bajo coste |

---

## Arrancar

```bash
python app.py
# → http://127.0.0.1:5000
```

O con la CLI directamente (sin interfaz web):

```bash
python main.py "Mai CDMO" --website mai-cdmo.com --pdf deck.pdf
```

---

## Cómo funciona

El sistema ejecuta un pipeline de 6 pasos de forma automática:

```
INPUT (empresa + web opcional + PDF opcional)
  │
  ▼
[1] WEB SEARCH — DuckDuckGo
    Lanza 4–5 queries en paralelo y recoge hasta 10 resultados cada una.
    Deduplica por URL y prioriza por patrones (web oficial, LinkedIn, registros).
  │
  ▼
[2] WEB FETCH — requests + BeautifulSoup
    Descarga las primeras 12 URLs. Extrae texto limpio (sin nav/footer/scripts).
    Cachea en SQLite: si la URL ya fue descargada, no la vuelve a pedir.
  │
  ▼
[3] PDF PROCESSOR — pdfplumber  (si se adjunta PDF)
    Extrae texto página a página, tablas y metadata.
    Detecta secciones automáticamente por encabezados.
  │
  ▼
[4] DATA ANALYZER — regex + NLP
    Extrae de cada fuente:
      • Dinero (€, $, K/M/B)     • Porcentajes
      • Personas (nombres propios) • Emails
      • CIF/NIF                   • Fechas
      • Métricas: revenue, funding, valuation, CAGR, empleados, fundación
    Consolida multi-fuente y detecta contradicciones entre fuentes.
  │
  ▼
[5] LLM SYNTHESIS — Claude API  (si hay API key)
    Envía los datos estructurados + snippets de texto a Claude.
    Claude genera: resumen ejecutivo, puntos clave, señales de alerta,
    próximos pasos recomendados.
  │
  ▼
[6] REPORT GENERATOR — Jinja2
    Genera tres archivos en output/:
      • [empresa]_report.md   — Markdown con TOC completo
      • [empresa]_report.html — HTML con estilos, listo para abrir
      • [empresa]_data.json   — Todos los datos crudos en JSON

OUTPUT
```

### Cache

Las páginas descargadas se guardan en `cache/fetch_cache.db` (SQLite).
La próxima vez que se investigue la misma URL, se recupera del cache sin hacer
ninguna petición HTTP. Útil para re-analizar sin gastar tiempo/ancho de banda.

Para vaciar el cache: simplemente borra `cache/fetch_cache.db`.

### Rate limiting

- Entre queries de búsqueda: **1.5 segundos**
- Entre descargas de páginas: **1.0 segundo**
- Evita bloqueos de DuckDuckGo y servidores web.

---

## Uso — Interfaz web

Abre `http://127.0.0.1:5000` en el navegador.

### Header

| Elemento | Función |
|----------|---------|
| Dropdown modelo | Cambia el modelo Claude para síntesis y chat |
| 🔑 API Key | Abre modal para introducir tu clave de Anthropic |
| Punto de estado | Gris=idle · Azul parpadeando=investigando · Verde=listo · Rojo=error |

### Chat — comandos de investigación

Escribe cualquiera de estas formas en el input:

```
/research "Mai CDMO" web:mai-cdmo.com
/research "Ferrovial"
/investiga "Empresa" web:empresa.com
investiga "Empresa"
busca "Empresa"
```

Con PDF adjunto: pulsa **📎**, selecciona el archivo, luego escribe el comando.

### Chat — preguntas libres

Una vez terminada la investigación, escribe en lenguaje natural:

```
¿Cuánto capital tiene?
¿Quién es el CEO?
¿Cuántos empleados tiene?
Resume el modelo de negocio
¿Qué riesgos ves como inversor?
```

Claude responde usando los datos extraídos de la investigación.

### Ver el reporte

Cuando termina la investigación aparece el botón **Ver reporte ↗**.
Abre el informe HTML a pantalla completa. Cierra con **✕** o pulsando **Esc**.

Los archivos también están disponibles en `output/` para descargar.

---

## Uso — CLI

```bash
# Básico
python main.py "Mai CDMO"

# Con web y PDF
python main.py "Mai CDMO" --website mai-cdmo.com --pdf deck.pdf

# Con queries adicionales
python main.py "Mai CDMO" -q "Mai CDMO patentes" -q "Mai CDMO clientes"

# Fetch paralelo (más rápido, puede provocar rate limits)
python main.py "Ferrovial" --async-fetch

# Región de búsqueda distinta
python main.py "Airbnb" --region us-en

# Sin HTML (solo MD + JSON)
python main.py "Mai CDMO" --no-html

# Log detallado
python main.py "Mai CDMO" --verbose
```

---

## Uso — API programática

```python
from main import run

# Mínimo
result = run("Mai CDMO")

# Completo
result = run(
    company_name  = "Mai CDMO",
    website       = "mai-cdmo.com",
    pdf_path      = "deck.pdf",
    queries       = ["Mai CDMO patentes", "Mai CDMO clientes clave"],
    region        = "es-es",
    async_fetch   = False,
    anthropic_key = "sk-ant-...",           # opcional, usa .env si no se pasa
    progress_callback = print,              # función que recibe mensajes de log
)

# result es un dict con:
# result["financial"]       → métricas financieras
# result["aggregated"]      → personas, emails, fechas, etc.
# result["per_source"]      → datos por cada URL procesada
# result["contradictions"]  → contradicciones detectadas entre fuentes
# result["llm_summary"]     → texto de síntesis de Claude
# result["_output_paths"]   → {"md": "...", "html": "...", "json": "..."}
```

---

## Queries actuales

Cuando se investiga una empresa, el sistema lanza estas queries automáticamente:

| # | Query generada | Objetivo |
|---|----------------|----------|
| 0 | `site:empresa.com` | Rastrear la web oficial (solo si se pasa `--website`) |
| 1 | `"Empresa" empresa` | Información corporativa general |
| 2 | `"Empresa" CEO founder equipo directivo` | Equipo y fundadores |
| 3 | `"Empresa" financiación inversión ronda` | Rondas de inversión y funding |
| 4 | `"Empresa" revenue ingresos facturación` | Métricas financieras |

Las URLs resultantes se priorizan en este orden:
1. Dominio oficial (si se pasa `--website`)
2. LinkedIn
3. Crunchbase
4. datoscif.es
5. informa.es
6. boe.es
7. Resto de resultados

> Las queries se pueden ampliar en cada llamada pasando `--query "texto adicional"`
> (CLI) o el array `queries=["..."]` (API programática).

---

## Estructura de archivos

```
research-system/
│
├── main.py                    ← Orquestador + CLI (click)
├── app.py                     ← Servidor Flask (web UI + API REST)
├── config.py                  ← Configuración global (lee .env)
├── requirements.txt
├── .env.example               ← Plantilla de variables de entorno
│
├── scrapers/
│   ├── search.py              ← WebSearcher: DuckDuckGo, multi-query, priorización
│   ├── fetch.py               ← WebFetcher: HTTP, cache SQLite, texto limpio
│   └── pdf_processor.py       ← PDFProcessor: texto, tablas, secciones
│
├── processors/
│   ├── analyzer.py            ← DataAnalyzer: regex, entidades, métricas financieras
│   └── report_generator.py    ← ReportGenerator: Jinja2 → .md + .html
│
├── llm/
│   └── synthesis.py           ← LLMSynthesizer: síntesis y chat con Claude
│
├── templates/
│   └── report.md.jinja2       ← Plantilla del informe Markdown
│
├── web_templates/
│   └── index.html             ← Frontend (chat-only, SSE, reporte fullscreen)
│
├── cache/
│   └── fetch_cache.db         ← SQLite: cache de páginas descargadas (auto)
│
└── output/                    ← Reportes generados
    ├── [empresa]_report.md
    ├── [empresa]_report.html
    └── [empresa]_data.json
```

---

## Roadmap / Próximas mejoras

### Selección de queries en el chat (menú)

**Situación actual:** las 4 queries base se generan automáticamente a partir del
nombre de empresa. El usuario puede añadir queries extra solo por CLI (`--query`)
o API (`queries=[...]`).

**Mejora propuesta:** mostrar en el chat, antes de lanzar la búsqueda, un menú
interactivo con las queries que se van a ejecutar. El usuario puede:

- Activar / desactivar queries individuales con checkboxes
- Editar el texto de una query antes de lanzarla
- Añadir queries propias desde el menú sin conocer la sintaxis CLI
- Guardar perfiles de queries para tipos de investigación habituales
  (due diligence, análisis competitivo, búsqueda de contactos, etc.)

**Queries candidatas a añadir al menú:**

| Categoría | Query |
|-----------|-------|
| Registro mercantil | `"Empresa" datoscif site:datoscif.es` |
| LinkedIn empresa | `"Empresa" site:linkedin.com/company` |
| LinkedIn equipo | `"Empresa" CEO site:linkedin.com/in` |
| Noticias recientes | `"Empresa" 2024 2025 noticias` |
| Competidores | `"Empresa" competidores alternativas sector` |
| Clientes / casos de uso | `"Empresa" clientes casos de uso testimonios` |
| Patentes / tecnología | `"Empresa" patentes tecnología I+D` |
| Crunchbase / funding | `"Empresa" site:crunchbase.com` |
| Regulatorio / legal | `"Empresa" regulación licencia sanción` |

**Implementación prevista:**
- Cuando el usuario escribe `/research "Empresa"`, el chat muestra una burbuja
  con checkboxes antes de lanzar (no lanza inmediatamente).
- Botón "Lanzar con estas queries" confirma y arranca el pipeline.
- En `app.py`: nuevo endpoint `POST /api/queries/preview` que devuelve las
  queries que se generarían para una empresa dada.
- En `main.py`: `_build_queries()` acepta `disabled_queries: list[str]` para
  omitir las desmarcadas.

---

### Búsquedas globales (sin empresa)

**Situación actual:** el sistema siempre requiere un nombre de empresa como
punto de partida. No hay modo de búsqueda libre.

**Mejora propuesta:** permitir búsquedas de tema libre sin estructura de empresa:

```
/buscar mercado CDMO España tendencias 2025
/buscar regulación IVD Europa
/buscar "valoración startups biotech" 2024
```

**Comportamiento esperado:**
1. Se lanza la query tal cual (sin envolver en `"empresa" ...`).
2. Se rastrean los primeros N resultados.
3. Claude sintetiza el tema libremente (sin plantilla de due diligence).
4. El reporte usa una plantilla diferente: `report_topic.md.jinja2`, con secciones
   de resumen, fuentes, datos clave y conclusiones.
5. El chat posterior puede seguir haciendo preguntas sobre el tema.

**Implementación prevista:**
- Nuevo comando `/buscar <query libre>` reconocido en el parser del frontend.
- En `main.py`: nueva clase `TopicResearcher` (o modo `topic=True` en
  `ResearchSystem`) que salta la generación de queries estructuradas y pasa la
  query directamente a `WebSearcher.search()`.
- En `llm/synthesis.py`: nuevo prompt de sistema para síntesis temática libre.
- Nueva plantilla `templates/report_topic.md.jinja2`.

---

*Research AI — generado con Claude Code*
