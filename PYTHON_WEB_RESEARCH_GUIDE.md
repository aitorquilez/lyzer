# GUÍA COMPLETA: Replicar Búsqueda Web en Python

**Objetivo:** Crear un sistema que replique cómo Rodolfo busca información (web search + fetch + análisis)

**Nivel:** Intermedio-Avanzado (requires Python 3.8+)

---

## 📋 TABLA DE CONTENIDOS

1. [Arquitectura General](#arquitectura-general)
2. [Stack de Tecnologías](#stack-de-tecnologías)
3. [Instalación y Setup](#instalación-y-setup)
4. [Paso 1: Web Search](#paso-1-web-search)
5. [Paso 2: Web Fetch](#paso-2-web-fetch)
6. [Paso 3: PDF Processing](#paso-3-pdf-processing)
7. [Paso 4: Data Analysis](#paso-4-data-analysis)
8. [Paso 5: Output Generation](#paso-5-output-generation)
9. [Arquitectura Completa](#arquitectura-completa)
10. [Prompt para IA de Código](#prompt-para-ia-de-código)

---

## 🏗️ ARQUITECTURA GENERAL

```
┌─────────────────────────────────────────────────────┐
│              WEB RESEARCH SYSTEM                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  INPUT: Nombre empresa + URL                        │
│    ↓                                                │
│  PASO 1: WEB SEARCH (DuckDuckGo)                   │
│    ├─ Query múltiples                              │
│    ├─ Parse resultados                             │
│    └─ Priorizar URLs                               │
│    ↓                                                │
│  PASO 2: WEB FETCH (BeautifulSoup/Requests)       │
│    ├─ GET cada URL                                 │
│    ├─ Extract texto limpio                         │
│    └─ Cache local                                  │
│    ↓                                                │
│  PASO 3: PDF PROCESSING                            │
│    ├─ Si hay PDF: pypdf / pdfplumber               │
│    └─ Extract + structure                          │
│    ↓                                                │
│  PASO 4: DATA ANALYSIS                             │
│    ├─ Parse datos (números, fechas, personas)      │
│    ├─ Normalize información                        │
│    └─ Structure en JSON/database                   │
│    ↓                                                │
│  PASO 5: REPORT GENERATION                         │
│    ├─ Template Markdown                            │
│    ├─ LLM synthesis (optional: OpenAI/Claude)      │
│    └─ Output: MD / HTML / PDF                      │
│    ↓                                                │
│  OUTPUT: Informe estructurado                      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ STACK DE TECNOLOGÍAS

| Layer | Librería | Propósito | Alternativas |
|-------|----------|-----------|--------------|
| **Search** | duckduckgo-search | Búsqueda web | google-search, bing |
| **HTTP** | requests | GET requests | httpx, aiohttp |
| **HTML Parse** | beautifulsoup4 | Extract texto | lxml, parsel |
| **PDF** | pdfplumber | PDF extraction | pypdf, pymupdf |
| **NLP/Text** | nltk, spacy | Clean text | TextBlob |
| **Data** | pandas | Estructurar datos | polars |
| **Cache** | redis OR sqlite | Cache local | diskcache |
| **LLM** | openai OR anthropic | Synthesis (optional) | huggingface |
| **Template** | jinja2 | Report generation | mako |
| **Export** | markdown2, fpdf | Output formats | reportlab |
| **Async** | asyncio, aiohttp | Paralelizar requests | httpx |
| **CLI** | click | Interface CLI | argparse |

---

## 🚀 INSTALACIÓN Y SETUP

### Crear entorno

```bash
# Python 3.8+
python -m venv research_env
source research_env/bin/activate  # Linux/Mac
# o: research_env\Scripts\activate  # Windows

# Instalar dependencias core
pip install requests beautifulsoup4 lxml pdfplumber pandas

# Instalar dependencias adicionales
pip install duckduckgo-search nltk asyncio aiohttp jinja2 markdown2

# Opcional: LLM synthesis
pip install openai anthropic

# Opcional: storage
pip install redis  # si usas Redis
pip install sqlite3  # ya viene en Python
```

### Estructura de carpetas

```
research-system/
├── main.py                  # Punto de entrada
├── config.py                # Configuración (API keys, paths)
├── scrapers/
│   ├── __init__.py
│   ├── search.py           # Web search
│   ├── fetch.py            # Web fetch
│   └── pdf_processor.py    # PDF extraction
├── processors/
│   ├── __init__.py
│   ├── parser.py           # Parse datos
│   ├── analyzer.py         # Análisis
│   └── normalizer.py       # Normalizar info
├── llm/
│   ├── __init__.py
│   └── synthesis.py        # LLM calls (optional)
├── templates/
│   └── report.md.jinja2    # Template reporte
├── cache/
│   └── .gitkeep            # Cache local
├── output/
│   └── .gitkeep            # Reportes output
└── requirements.txt         # Deps
```

---

## 🔍 PASO 1: WEB SEARCH

### Usando DuckDuckGo

```python
# scrapers/search.py

from duckduckgo_search import DDGS
import json
import time

class WebSearcher:
    def __init__(self, region="es-es", timeout=30):
        self.ddgs = DDGS(timeout=timeout)
        self.region = region
        self.results = []
    
    def search(self, query, max_results=10):
        """
        Query DuckDuckGo y retorna resultados estructurados
        
        Args:
            query (str): Término búsqueda
            max_results (int): Número resultados (default 10)
        
        Returns:
            list: [
                {
                    'title': str,
                    'url': str,
                    'snippet': str,
                    'source': str,
                }
            ]
        """
        try:
            results = self.ddgs.text(
                keywords=query,
                region=self.region,
                max_results=max_results
            )
            
            # Parse a estructura uniforme
            parsed = []
            for r in results:
                parsed.append({
                    'title': r.get('title', ''),
                    'url': r.get('href', ''),
                    'snippet': r.get('body', ''),
                    'source': r.get('source', 'DuckDuckGo'),
                    'query': query,
                    'timestamp': time.time()
                })
            
            self.results.extend(parsed)
            return parsed
        
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []
    
    def multi_search(self, queries, max_results=10):
        """
        Ejecuta múltiples queries
        
        Args:
            queries (list): Lista de queries
            max_results (int): Resultados por query
        
        Returns:
            list: Todos los resultados combinados
        """
        all_results = []
        for query in queries:
            print(f"🔍 Buscando: {query}")
            results = self.search(query, max_results)
            all_results.extend(results)
            time.sleep(1)  # Rate limit
        
        return all_results
    
    def prioritize_urls(self, results, priority_patterns):
        """
        Prioriza URLs según patrones
        
        Args:
            results (list): Resultados de búsqueda
            priority_patterns (list): Patrones a priorizar
                Ej: ['mai-cdmo.com', 'linkedin.com', 'datoscif.es']
        
        Returns:
            list: URLs ordenadas por prioritario
        """
        prioritized = []
        
        # Tier 1: Official/registry
        for pattern in priority_patterns:
            for r in results:
                if pattern in r['url'] and r not in prioritized:
                    prioritized.append(r)
        
        # Tier 2: Rest
        for r in results:
            if r not in prioritized:
                prioritized.append(r)
        
        return prioritized

# USO:
if __name__ == "__main__":
    searcher = WebSearcher(region="es-es")
    
    queries = [
        "Mai CDMO mai-cdmo.com empresa",
        "Mai CDMO CEO founder",
        "Mai CDMO financiación",
    ]
    
    results = searcher.multi_search(queries, max_results=10)
    
    priority = ['mai-cdmo.com', 'linkedin.com', 'datoscif.es']
    prioritized = searcher.prioritize_urls(results, priority)
    
    print(f"✅ Found {len(results)} results")
    print(f"📌 Top 5 prioritized:")
    for r in prioritized[:5]:
        print(f"  - {r['title'][:50]}...")
        print(f"    {r['url']}")
```

**Parámetros clave:**
- `region`: "es-es" para España, "us-en" para USA, etc.
- `max_results`: 5-100 típicamente
- `timeout`: segundos antes de timeout

---

## 📄 PASO 2: WEB FETCH

### Usando Requests + BeautifulSoup

```python
# scrapers/fetch.py

import requests
from bs4 import BeautifulSoup
from readability import Document
import time
import hashlib

class WebFetcher:
    def __init__(self, timeout=10, cache_dir="./cache"):
        self.timeout = timeout
        self.cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _get_cache_path(self, url):
        """Genera path de cache basado en URL"""
        hashed = hashlib.md5(url.encode()).hexdigest()
        return f"{self.cache_dir}/{hashed}.txt"
    
    def _check_cache(self, url):
        """Chequea si URL está en cache"""
        try:
            path = self._get_cache_path(url)
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            return None
    
    def _save_cache(self, url, content):
        """Guarda contenido en cache"""
        try:
            path = self._get_cache_path(url)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except:
            pass
    
    def fetch(self, url, use_readability=True, max_chars=5000):
        """
        Fetch URL y extrae texto limpio
        
        Args:
            url (str): URL a fetchar
            use_readability (bool): Usar readability parser
            max_chars (int): Máximo caracteres a retornar
        
        Returns:
            dict: {
                'url': str,
                'title': str,
                'content': str,
                'status': int,
                'cached': bool
            }
        """
        
        # Check cache
        cached = self._check_cache(url)
        if cached:
            return {
                'url': url,
                'content': cached[:max_chars],
                'cached': True,
                'status': 200
            }
        
        try:
            # Fetch
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            
            # Parse
            if use_readability:
                # Readability: extrae main content (más limpio)
                doc = Document(resp.text)
                content = doc.summary()
                title = doc.title()
            else:
                # BeautifulSoup: más manual
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Remove scripts/styles
                for script in soup(["script", "style", "nav", "footer"]):
                    script.decompose()
                
                # Extract text
                content = soup.get_text(separator='\n', strip=True)
                title = soup.find('title')
                title = title.string if title else ""
            
            # Limit chars
            content = content[:max_chars]
            
            # Save cache
            self._save_cache(url, content)
            
            return {
                'url': url,
                'title': title,
                'content': content,
                'status': resp.status_code,
                'cached': False
            }
        
        except requests.exceptions.Timeout:
            return {
                'url': url,
                'status': 408,
                'error': 'Timeout',
                'content': None
            }
        except requests.exceptions.ConnectionError:
            return {
                'url': url,
                'status': 0,
                'error': 'Connection error',
                'content': None
            }
        except Exception as e:
            return {
                'url': url,
                'status': 500,
                'error': str(e),
                'content': None
            }
    
    def fetch_multiple(self, urls, max_chars=5000, async_mode=False):
        """
        Fetch múltiples URLs
        
        Args:
            urls (list): URLs a fetchar
            max_chars (int): Max chars por página
            async_mode (bool): Usar requests asincronous
        
        Returns:
            list: Resultados
        """
        results = []
        
        if async_mode:
            # Async (más rápido pero más complejo)
            import asyncio
            import aiohttp
            
            async def fetch_async():
                async with aiohttp.ClientSession() as session:
                    tasks = [
                        self._fetch_async(session, url, max_chars)
                        for url in urls
                    ]
                    return await asyncio.gather(*tasks)
            
            results = asyncio.run(fetch_async())
        
        else:
            # Sync (más simple)
            for url in urls:
                print(f"📄 Fetching: {url}")
                result = self.fetch(url, max_chars=max_chars)
                results.append(result)
                time.sleep(0.5)  # Rate limit
        
        return results

# USO:
if __name__ == "__main__":
    fetcher = WebFetcher(timeout=10, cache_dir="./cache")
    
    urls = [
        "https://mai-cdmo.com",
        "https://www.datoscif.es/empresa/mai-cdmo-sl",
        "https://es.linkedin.com/company/mai-cdmo",
    ]
    
    results = fetcher.fetch_multiple(urls, max_chars=5000)
    
    for r in results:
        if r.get('content'):
            print(f"✅ {r['url']}")
            print(f"   {r['content'][:100]}...")
        else:
            print(f"❌ {r['url']}: {r.get('error', 'Unknown')}")
```

**Parámetros clave:**
- `timeout`: segundos antes de timeout
- `max_chars`: 5000-10000 típicamente
- `use_readability`: True para main content, False para full HTML
- `async_mode`: True para paralelizar (más rápido)

---

## 📕 PASO 3: PDF PROCESSING

### Usando pdfplumber

```python
# scrapers/pdf_processor.py

import pdfplumber
import json

class PDFProcessor:
    def __init__(self):
        pass
    
    def extract_text(self, pdf_path):
        """
        Extrae texto de PDF
        
        Args:
            pdf_path (str): Path al PDF
        
        Returns:
            dict: {
                'text': str,
                'pages': int,
                'metadata': dict
            }
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
                
                return {
                    'text': text,
                    'pages': len(pdf.pages),
                    'metadata': pdf.metadata
                }
        except Exception as e:
            return {'error': str(e)}
    
    def extract_tables(self, pdf_path):
        """
        Extrae tablas de PDF
        
        Args:
            pdf_path (str): Path al PDF
        
        Returns:
            list: Tablas como listas de dicts
        """
        try:
            tables = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        for table in page_tables:
                            tables.append({
                                'data': table,
                                'page': pdf.pages.index(page) + 1
                            })
            return tables
        except Exception as e:
            return []
    
    def extract_structured(self, pdf_path, sections=None):
        """
        Extrae contenido estructurado por secciones
        
        Args:
            pdf_path (str): Path al PDF
            sections (list): Secciones a extraer
                Ej: ['Problem', 'Solution', 'Team']
        
        Returns:
            dict: Contenido por sección
        """
        full_text = self.extract_text(pdf_path)
        
        if not sections:
            return full_text
        
        # Split por secciones
        structured = {}
        text = full_text.get('text', '')
        
        for section in sections:
            if section.lower() in text.lower():
                # Simple approach: find section y extrae hasta siguiente
                start = text.lower().find(section.lower())
                end = len(text)
                
                structured[section] = text[start:end][:1000]  # 1000 chars
        
        return structured

# USO:
if __name__ == "__main__":
    processor = PDFProcessor()
    
    # Extract text
    result = processor.extract_text("MAI_CDMO_Deck_v3.pdf")
    print(f"✅ Extracted {result['pages']} pages")
    print(result['text'][:500])
    
    # Extract tables
    tables = processor.extract_tables("MAI_CDMO_Deck_v3.pdf")
    print(f"📊 Found {len(tables)} tables")
    
    # Extract structured
    sections = ['Problem', 'Solution', 'Team', 'Market']
    structured = processor.extract_structured("MAI_CDMO_Deck_v3.pdf", sections)
```

---

## 📊 PASO 4: DATA ANALYSIS

### Parse y estructura información

```python
# processors/analyzer.py

import re
import json
from datetime import datetime
import pandas as pd

class DataAnalyzer:
    def __init__(self):
        self.extracted_data = {}
    
    def extract_numbers(self, text):
        """Extrae números (dinero, años, %ajes)"""
        patterns = {
            'money': r'€\s*([\d,\.]+[KMB]?)',
            'percentages': r'(\d+\.?\d*)%',
            'years': r'(19|20)\d{2}',
        }
        
        results = {}
        for key, pattern in patterns.items():
            results[key] = re.findall(pattern, text)
        
        return results
    
    def extract_people(self, text):
        """Extrae nombres de personas"""
        # Simple pattern: Capitalized words (no perfecto pero funciona)
        names = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
        return list(set(names))
    
    def extract_emails(self, text):
        """Extrae emails"""
        pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        return re.findall(pattern, text)
    
    def extract_urls(self, text):
        """Extrae URLs"""
        pattern = r'https?://[^\s]+'
        return re.findall(pattern, text)
    
    def extract_dates(self, text):
        """Extrae fechas"""
        patterns = [
            r'(\d{1,2})/(\d{1,2})/(\d{4})',  # DD/MM/YYYY
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
        ]
        
        dates = []
        for pattern in patterns:
            dates.extend(re.findall(pattern, text))
        
        return dates
    
    def parse_financial_metrics(self, text):
        """Extrae métricas financieras"""
        metrics = {
            'revenue': self._find_value(text, r'revenue.*?(€[\d,\.]+[KMB]?)'),
            'funding': self._find_value(text, r'funding.*?(€[\d,\.]+[KMB]?)'),
            'valuation': self._find_value(text, r'valuation.*?(€[\d,\.]+[KMB]?)'),
            'cagr': self._find_value(text, r'CAGR.*?(\d+\.?\d*)%'),
        }
        return metrics
    
    def _find_value(self, text, pattern):
        """Helper: encuentra primer match"""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else None
    
    def consolidate(self, sources):
        """
        Consolida info de múltiples fuentes
        
        Args:
            sources (dict): {
                'website': text,
                'registry': text,
                'linkedin': text,
                'pdf': text
            }
        
        Returns:
            dict: Datos consolidados
        """
        consolidated = {
            'numbers': {},
            'people': {},
            'money': {},
            'dates': {},
            'urls': {},
        }
        
        for source_name, source_text in sources.items():
            numbers = self.extract_numbers(source_text)
            people = self.extract_people(source_text)
            emails = self.extract_emails(source_text)
            urls = self.extract_urls(source_text)
            dates = self.extract_dates(source_text)
            financial = self.parse_financial_metrics(source_text)
            
            consolidated['numbers'][source_name] = numbers
            consolidated['people'][source_name] = people
            consolidated['emails'] = list(set(consolidated.get('emails', []) + emails))
            consolidated['urls'][source_name] = urls
            consolidated['dates'][source_name] = dates
            consolidated['financial'] = {**consolidated.get('financial', {}), **financial}
        
        return consolidated

# USO:
if __name__ == "__main__":
    analyzer = DataAnalyzer()
    
    sources = {
        'website': "MAI CDMO is a €300K funded startup...",
        'registry': "CIF: B19856293, Capital: €30,000...",
        'pdf': "Revenue: €19,600, Team size: 8...",
    }
    
    consolidated = analyzer.consolidate(sources)
    print(json.dumps(consolidated, indent=2, ensure_ascii=False))
```

---

## 📝 PASO 5: OUTPUT GENERATION

### Template + Report Generation

```python
# processors/report_generator.py

from jinja2 import Template
from datetime import datetime
import markdown2

class ReportGenerator:
    def __init__(self, template_path="templates/report.md.jinja2"):
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = Template(f.read())
    
    def generate(self, data, output_path="output/report.md"):
        """
        Genera reporte
        
        Args:
            data (dict): Datos a incluir
            output_path (str): Path de output
        
        Returns:
            str: Contenido del reporte
        """
        
        # Add timestamp
        data['generated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Render template
        content = self.template.render(data)
        
        # Save
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Report generated: {output_path}")
        
        return content
    
    def to_html(self, md_content, output_path="output/report.html"):
        """Convierte Markdown a HTML"""
        html = markdown2.markdown(md_content, extras=['tables', 'fenced-code-blocks'])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    h1 {{ color: #333; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                </style>
            </head>
            <body>
                {html}
            </body>
            </html>
            """)
        
        return output_path

# templates/report.md.jinja2
TEMPLATE = """
# {{ company_name }} - Análisis Completo

**Generado:** {{ generated_at }}

## Información Corporativa

- **CIF:** {{ cif }}
- **Capital:** {{ capital }}
- **Ubicación:** {{ location }}
- **Status:** {{ status }}

## Financiero

{% if financial %}
| Métrica | Valor |
|--------|-------|
{% for key, value in financial.items() %}
| {{ key }} | {{ value }} |
{% endfor %}
{% endif %}

## Equipo

{% if people %}
{% for name in people %}
- {{ name }}
{% endfor %}
{% endif %}

## Datos Extraídos

### Números
- {{ numbers }}

### URLs
- {{ urls }}

---

*Análisis automático - Para validación de datos, require due diligence manual*
"""
```

---

## 🎯 ARQUITECTURA COMPLETA

```python
# main.py

from scrapers.search import WebSearcher
from scrapers.fetch import WebFetcher
from scrapers.pdf_processor import PDFProcessor
from processors.analyzer import DataAnalyzer
from processors.report_generator import ReportGenerator
import json

class ResearchSystem:
    def __init__(self):
        self.searcher = WebSearcher(region="es-es")
        self.fetcher = WebFetcher(timeout=10, cache_dir="./cache")
        self.pdf_processor = PDFProcessor()
        self.analyzer = DataAnalyzer()
        self.report_gen = ReportGenerator()
    
    def research(self, company_name, website, queries=None, pdf_path=None):
        """
        Ejecuta investigación completa
        
        Args:
            company_name (str): Nombre empresa
            website (str): URL principal
            queries (list): Búsquedas adicionales
            pdf_path (str): Path a PDF (opcional)
        
        Returns:
            dict: Datos consolidados
        """
        
        print(f"\n🔍 Iniciando investigación: {company_name}")
        
        # PASO 1: SEARCH
        print("\n1️⃣  Búsqueda web...")
        if not queries:
            queries = [
                f"{company_name} empresa",
                f"{company_name} CEO founder",
                f"{company_name} financiación",
            ]
        
        search_results = self.searcher.multi_search(queries, max_results=10)
        
        # PASO 2: PRIORITIZE URLs
        priority_patterns = [website, 'linkedin.com', 'crunchbase.com', 'datoscif.es']
        prioritized = self.searcher.prioritize_urls(search_results, priority_patterns)
        
        # PASO 3: FETCH
        print("\n2️⃣  Extrayendo contenido...")
        urls_to_fetch = [r['url'] for r in prioritized[:10]]
        fetch_results = self.fetcher.fetch_multiple(urls_to_fetch, max_chars=5000)
        
        # PASO 4: PDF (si existe)
        pdf_content = None
        if pdf_path:
            print(f"\n3️⃣  Procesando PDF...")
            pdf_content = self.pdf_processor.extract_text(pdf_path)
        
        # PASO 5: ANALYZE
        print("\n4️⃣  Analizando datos...")
        sources = {}
        for i, result in enumerate(fetch_results):
            if result.get('content'):
                sources[f"source_{i}"] = result['content']
        
        if pdf_content:
            sources['pdf'] = pdf_content['text']
        
        consolidated = self.analyzer.consolidate(sources)
        
        # PASO 6: GENERATE REPORT
        print("\n5️⃣  Generando reporte...")
        report_data = {
            'company_name': company_name,
            'website': website,
            'financial': consolidated.get('financial', {}),
            'people': consolidated.get('people', {}),
            'numbers': consolidated.get('numbers', {}),
            'urls': consolidated.get('urls', {}),
            'search_results': len(search_results),
            'sources_analyzed': len(sources),
        }
        
        report = self.report_gen.generate(report_data, f"output/{company_name}_report.md")
        self.report_gen.to_html(report, f"output/{company_name}_report.html")
        
        print(f"\n✅ Investigación completada!")
        print(f"📄 Reporte: output/{company_name}_report.md")
        
        return consolidated

# USO:
if __name__ == "__main__":
    system = ResearchSystem()
    
    result = system.research(
        company_name="MAI CDMO",
        website="mai-cdmo.com",
        pdf_path="MAI_CDMO_Investment_Deck_v3.pdf"
    )
    
    print("\n📊 Resumen:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

---

## 🤖 PROMPT PARA IA DE CÓDIGO

**Usa este prompt en Cursor, Claude Code, o GitHub Copilot para generar el código:**

```
Crea un sistema de investigación web en Python que replique cómo busco información online.

REQUISITOS:

1. **Web Search Module**
   - Usa duckduckgo-search para búsquedas
   - Permite múltiples queries paralelas
   - Retorna: title, url, snippet, source
   - Prioritiza URLs por patrones (website, linkedin, registry)

2. **Web Fetcher Module**
   - Usa requests + BeautifulSoup (o readability-lxml)
   - GET cada URL, extrae texto limpio
   - Cache local (archivo o SQLite)
   - Maneja timeouts y errores
   - Retorna: url, title, content (max 5000 chars), status

3. **PDF Processor Module**
   - Usa pdfplumber
   - Extrae: texto completo, tablas, metadata
   - Permite extracción por secciones

4. **Data Analyzer Module**
   - Parse: números, dinero (€), fechas, personas, emails, URLs
   - Extrae métricas financieras (revenue, funding, valuation, CAGR)
   - Consolida datos de múltiples fuentes
   - Detecta y maneja contradicciones

5. **Report Generator Module**
   - Template Jinja2 para Markdown
   - Genera reporte estructurado
   - Exporta a HTML opcional
   - Incluye timestamp, resumen, tabla de contenidos

6. **Main Orchestrator**
   - Executa flujo completo: search → fetch → analyze → report
   - Paraleliza requests donde sea posible
   - Logging + progress indicators
   - CLI interface (opcional: click)

ESTRUCTURA DE CARPETAS:
```
research-system/
├── main.py
├── config.py
├── requirements.txt
├── scrapers/
│   ├── search.py
│   ├── fetch.py
│   └── pdf_processor.py
├── processors/
│   ├── analyzer.py
│   └── report_generator.py
├── templates/
│   └── report.md.jinja2
├── cache/
└── output/
```

PUNTOS CLAVE:
- Rate limiting (espera entre requests)
- Error handling robusto
- Cache local para no re-fetchar
- Async cuando sea posible
- User-Agent headers
- Máximo 5000 caracteres por página

EJEMPLO DE USO:
```python
system = ResearchSystem()
result = system.research(
    company_name="Mai CDMO",
    website="mai-cdmo.com",
    pdf_path="deck.pdf"
)
```

OUTPUT:
- Markdown report: output/[company]_report.md
- HTML report: output/[company]_report.html
- JSON data: output/[company]_data.json

Código limpio, comentado, production-ready.
```

---

## 🎓 COMPARATIVA: Mi Sistema vs Tu Python

| Aspecto | Rodolfo | Tu Python |
|---------|---------|-----------|
| **Search** | DuckDuckGo API (OpenClaw) | duckduckgo-search lib |
| **Fetch** | Readability (OpenClaw) | BeautifulSoup/requests |
| **PDF** | Claude nativo | pdfplumber |
| **Analysis** | Reasoning nativo | regex + NLP libs |
| **Speed** | ~30 sec profundo | ~2-3 min profundo |
| **Parallelization** | Automático | asyncio manual |
| **LLM synthesis** | Claude integrado | OpenAI API optional |

**Mi ventaja:** Integración nativa, menos setup, más rápido.  
**Tu ventaja:** Control total, customizable, corre local, sin API costs.

---

## 💡 PRÓXIMOS PASOS

1. **Install dependencies:** `pip install -r requirements.txt`
2. **Setup config.py** (API keys si usas LLM)
3. **Test cada módulo** por separado
4. **Run main.py** con ejemplo
5. **Customiza templates** según necesidad
6. **Add logging** para debugging

---

**FIN DE GUÍA**

*Esta guía te permite replicar ~80% de lo que hago. El 20% restante (razonamiento LLM) requiere integración con OpenAI/Claude API.*
