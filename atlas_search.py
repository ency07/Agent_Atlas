#!/usr/bin/env python3
"""
Atlas Search MCP Server — Búsqueda web + investigación profunda.

Provee:
  - web_search(query, max_results) → resultados de búsqueda (DuckDuckGo + SearXNG fallback)
  - web_research(topic, depth) → investigación profunda con informe en bóveda

Configuración en state/search.json:
  {
    "searxng_url": "http://localhost:8080",  # opcional, si está levantado
    "timeout_ddgs": 15,
    "timeout_searxng": 10,
    "max_results": 10
  }

Requiere: ddgs (pip install ddgs)
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from mcp.server.fastmcp import FastMCP

try:
    from ddgs import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

# --- Paths ---
MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path(__file__).parent / "memory_data"))).resolve()
STATE_DIR = MEMORY_ROOT / "state"
SEARCH_CONFIG = STATE_DIR / "search.json"

# --- Config ---
DEFAULT_CONFIG = {
    "searxng_url": "",  # vacio = deshabilitado
    "timeout_ddgs": 15,
    "timeout_searxng": 10,
    "max_results": 10,
}

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(MEMORY_ROOT / "logs" / "atlas_search.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("atlas_search")

# --- MCP Server ---
mcp = FastMCP("atlas_search", host="127.0.0.1", port=4099)

# --- Config loader ---
def load_config() -> Dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not SEARCH_CONFIG.exists():
        SEARCH_CONFIG.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    try:
        return json.loads(SEARCH_CONFIG.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning(f"config invalida, usando default: {exc}")
        return DEFAULT_CONFIG.copy()

config = load_config()

# --- Search Providers ---

def ddgs_search(query: str, max_results: int) -> List[Dict]:
    """Búsqueda DuckDuckGo via lib ddgs (sin API key)."""
    if not HAS_DDGS:
        return []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, timeout=config["timeout_ddgs"]))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                    "source": "ddgs",
                }
                for r in results
            ]
    except Exception as exc:
        log.warning(f"ddgs fallo: {exc}")
        return []


def searxng_search(query: str, max_results: int) -> List[Dict]:
    """Búsqueda SearXNG (self-hosted o publico)."""
    url = config["searxng_url"].strip()
    if not url:
        return []
    try:
        import httpx
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
            "language": "es",
        }
        r = httpx.get(f"{url}/search", params=params, timeout=config["timeout_searxng"])
        r.raise_for_status()
        data = r.json()
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "source": "searxng",
            }
            for r in data.get("results", [])[:max_results]
        ]
    except Exception as exc:
        log.warning(f"searxng fallo: {exc}")
        return []


def ddg_html_search(query: str, max_results: int) -> List[Dict]:
    """Fallback duro: DuckDuckGo HTML scrape (sin lib)."""
    try:
        import httpx
        from bs4 import BeautifulSoup
        params = {"q": query}
        r = httpx.get("https://html.duckduckgo.com/html/", params=params, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for div in soup.select("div.result__body")[:max_results]:
            a = div.select_one("a.result__a")
            if a:
                results.append({
                    "title": a.text.strip(),
                    "url": a["href"],
                    "snippet": div.select_one("a.result__snippet").text.strip() if div.select_one("a.result__snippet") else "",
                    "source": "ddg_html",
                })
        return results
    except Exception as exc:
        log.warning(f"ddg_html fallo: {exc}")
        return []


# --- MCP Tools ---

@mcp.tool()
def web_search(query: str, max_results: int = 10) -> List[Dict]:
    """Busca en internet con cadena de respaldo: DuckDuckGo → SearXNG → DuckDuckGo HTML.
    
    Args:
        query: Término de búsqueda
        max_results: Máximo de resultados (default 10)
        
    Returns:
        Lista de resultados: [{"title": str, "url": str, "snippet": str, "source": str}]
    """
    results = []
    
    # DuckDuckGo (lib ddgs)
    if not results:
        results = ddgs_search(query, max_results)
    
    # SearXNG (self-hosted)
    if not results and config["searxng_url"]:
        results = searxng_search(query, max_results)
    
    # DuckDuckGo HTML (fallback duro)
    if not results:
        results = ddg_html_search(query, max_results)
    
    return results


@mcp.tool()
def web_research(topic: str, depth: int = 1) -> Dict:
    """Investigación profunda: busca, lee fuentes, sintetiza informe y guarda en bóveda.
    
    Args:
        topic: Tema de investigación
        depth: Profundidad (1 = ronda única, 2-3 = investigación multi-ronda)
        
    Returns:
        {
            "summary": str,  # resumen ejecutivo
            "note_path": str,  # ruta de la nota en la bóveda
            "sources": List[str],  # URLs de las fuentes
        }
    """
    from mcp_memory_server import tool_note_save
    
    # Ronda 1: búsqueda inicial
    results = web_search(topic, max_results=10)
    if not results:
        return {"summary": f"No se encontraron resultados para '{topic}'", "note_path": "", "sources": []}
    
    # Leer contenido de las fuentes
    sources_content = []
    for r in results[:5]:  # top 5
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(r["url"], timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            content = soup.get_text(separator=" ", strip=True)[:8000]
            sources_content.append({
                "url": r["url"],
                "title": r["title"],
                "content": content,
            })
        except Exception as exc:
            log.warning(f"no se pudo leer {r['url']}: {exc}")
    
    # Extraer hechos clave
    facts = []
    for src in sources_content:
        # TODO: usar LLM para extraer hechos (hoy extracción simple)
        facts.append(f"Fuente: {src['title']} ({src['url']})\n{src['content'][:500]}...")
    
    # Ronda 2+ (si depth > 1)
    follow_ups = []
    if depth > 1:
        # Generar preguntas de seguimiento
        # TODO: usar LLM para generar preguntas (hoy hardcoded)
        follow_ups = [f"{topic} causas", f"{topic} consecuencias", f"{topic} ejemplos"]
        for q in follow_ups:
            results2 = web_search(q, max_results=5)
            for r in results2:
                try:
                    import requests
                    from bs4 import BeautifulSoup
                    resp = requests.get(r["url"], timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                        tag.decompose()
                    content = soup.get_text(separator=" ", strip=True)[:5000]
                    facts.append(f"Fuente (seguimiento): {r['title']} ({r['url']})\n{content[:300]}...")
                except Exception:
                    pass
    
    # Sintetizar informe
    summary = f"Informe sobre '{topic}'\n\n"
    summary += "\n".join(facts[:10])  # top 10 hechos
    
    # Guardar en bóveda
    note_title = f"Investigación - {topic[:50]}"
    note_body = f"# {note_title}\n\n**Resumen**\n{summary}\n\n**Fuentes**\n" + "\n".join([f"- [{src['title']}]({src['url']})" for src in sources_content])
    
    note = tool_note_save(
        title=note_title,
        body=note_body,
        type="research",
        project="global",
        tags="investigacion,web",
        links="",
    )
    note_path = ""
    try:
        note_path = json.loads(note).get("path", "")
    except Exception:
        note_path = ""
    
    return {
        "summary": summary,
        "note_path": note_path,
        "sources": [r["url"] for r in results],
    }


# --- Main ---
if __name__ == "__main__":
    mcp.run(transport="stdio")