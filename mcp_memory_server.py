#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP Memory Server — Atlas (Fase 1)
===================================
Servidor MCP (FastMCP) de memoria persistente con cerebro tipo Obsidian.

Estructura (raiz configurable via env MEMORY_ROOT, default: este directorio):
  <MEMORY_ROOT>/vault/                       <- boveda Obsidian (fuente de verdad humana)
      global/                                <- memoria global (preferencias, identidad)
      <proyecto>/                            <- una por proyecto
          MEMORY.md                          <- indice (SIEMPRE ligero, ~30 lineas)
          notes/ decisions/ facts/ sessions/ <- notas markdown con frontmatter
          graph.json                         <- grafo derivado (reconstruible)
  <MEMORY_ROOT>/state/memory.db              <- SQLite (canonico: events/sessions/indices/FTS5)
  <MEMORY_ROOT>/inbox/                       <- cola de eventos crudos (git hook, futuros daemons)

Uso:
  - MCP (interactivo): python mcp_memory_server.py
  - CLI hook (git post-commit, no bloquea):
      python mcp_memory_server.py --hook-event '{"type":"commit","project":"x","data":{...}}'
  - CLI de mantenimiento/validacion:
      python mcp_memory_server.py --cli init [proyecto] [--project-root RUTA]
      python mcp_memory_server.py --cli health

Convenciones:
  - El server NUNCA escribe fuera de <MEMORY_ROOT>. NUNCA ejecuta comandos.
  - Las notas son .md con frontmatter YAML (abre directamente en Obsidian).
  - El grafo se DERIVA de frontmatter + wikilinks ([[...]]) -> graph.json.
  - Redaccion de secretos en toda escritura (sk-..., token=..., passwords...).
"""

import json
import os
import re
import shutil
import sqlite3
import sys
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

MEMORY_ROOT = Path(os.environ.get("MEMORY_ROOT", str(Path(__file__).parent / "memory_data"))).resolve()
VAULT_ROOT = MEMORY_ROOT / "vault"
STATE_DIR = MEMORY_ROOT / "state"
INBOX_DIR = MEMORY_ROOT / "inbox"
DB_PATH = STATE_DIR / "memory.db"
IDENTITY_PATH = VAULT_ROOT / "global" / "preferences" / "identity.md"
PREF_DIR = VAULT_ROOT / "global" / "preferences"

NOTE_TYPES = ("decision", "fact", "preference", "summary", "opportunity",
              "task", "risk", "lesson", "session", "event")

DEFAULT_IDENTITY = """---
type: preference
category: identity
---
Eres Atlas. Socio operativo del usuario.
- No halagas. No uses emojis excesivos.
- Datos concretos antes que opiniones.
- Si detectas distraccion o fuga de tiempo, lo dices sin rodeos.
- Cada respuesta debe apuntar a: ganar dinero, ahorrar tiempo o reducir riesgo.
- Nombre configurable: edita este archivo y reinicia la sesion.
"""

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b[0-9]{13,16}\b"),
    re.compile(r"(?i)\b(password|passwd|secret|token|api[-_]?key|access[-_]?key|bearer)\b\s*[=:]\s*[^\s,;]+"),
    re.compile(r"(?i)\b(bearer|token)\b\s+[A-Za-z0-9._~+/=-]{10,}"),
    re.compile(r"(?i)(-----BEGIN [A-Z ]*PRIVATE KEY-----)"),
]

def redact(text: str) -> str:
    if not text:
        return text
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text

def clean_value(value) -> str:
    if isinstance(value, (dict, list)):
        return redact(json.dumps(value, ensure_ascii=False))
    return redact(str(value))

def safe_project(project: str) -> str:
    p = re.sub(r"[^A-Za-z0-9._-]", "-", str(project).strip().lower())
    return p or "proyecto"

def project_dir(project: str) -> Path:
    p = safe_project(project)
    d = (VAULT_ROOT / p).resolve()
    if not str(d).startswith(str(VAULT_ROOT.resolve())):
        raise ValueError("Ruta de proyecto fuera del vault: bloqueado")
    return d

def ensure_project(project: str) -> Path:
    d = project_dir(project)
    for sub in ("notes", "decisions", "facts", "sessions", "preferences"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def db_connect() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def db_init() -> None:
    conn = db_connect()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY,
          ts TEXT NOT NULL,
          source TEXT,
          type TEXT NOT NULL,
          project TEXT,
          app TEXT,
          window_title TEXT,
          category TEXT,
          monetizable INTEGER DEFAULT 0,
          risk TEXT,
          duration_seconds INTEGER,
          payload TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
        CREATE INDEX IF NOT EXISTS idx_events_project ON events(project);

        CREATE TABLE IF NOT EXISTS sessions (
          id TEXT PRIMARY KEY,
          project TEXT,
          started TEXT,
          ended TEXT,
          status TEXT DEFAULT 'active',
          summary TEXT,
          notes_count INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

        CREATE TABLE IF NOT EXISTS notes_index (
          id TEXT PRIMARY KEY,
          path TEXT,
          title TEXT,
          type TEXT,
          project TEXT,
          tags TEXT,
          created TEXT,
          status TEXT,
          links TEXT,
          summary TEXT
        );

        CREATE TABLE IF NOT EXISTS preferences (
          key TEXT PRIMARY KEY,
          value TEXT,
          scope TEXT DEFAULT 'global',
          project TEXT DEFAULT 'global',
          updated TEXT
        );

        CREATE TABLE IF NOT EXISTS graph_nodes (
          id TEXT PRIMARY KEY,
          label TEXT,
          type TEXT,
          project TEXT,
          properties TEXT
        );
        CREATE TABLE IF NOT EXISTS graph_edges (
          source TEXT,
          target TEXT,
          relation TEXT,
          project TEXT,
          PRIMARY KEY (source, target, relation)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(id, title, body);
        """)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(preferences)")]
        if "project" not in cols:
            conn.execute("ALTER TABLE preferences ADD COLUMN project TEXT DEFAULT 'global'")
        conn.commit()
    finally:
        conn.close()

def dbs() -> sqlite3.Connection:
    db_init()
    return db_connect()

def slugify(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]", "-", text.strip().lower())
    return re.sub(r"-+", "-", s).strip("-") or "nota"

def parse_frontmatter(body: str):
    fm, content = {}, body
    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end != -1:
            raw = body[4:end]
            content = body[end + 4:].lstrip("\n")
            for line in raw.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip('"')
    return fm, content

def note_to_index(d: Path, project: str):
    try:
        text = d.read_text(encoding="utf-8")
    except Exception:
        return None
    fm, content = parse_frontmatter(text)
    nid = fm.get("id") or d.stem
    links = re.findall(r"\[\[([^\]]+)\]\]", text)
    return {
        "id": nid, "path": str(d), "title": fm.get("title", d.stem),
        "type": fm.get("type", "fact"), "project": project,
        "tags": fm.get("tags", ""), "created": fm.get("created", now_iso()),
        "status": fm.get("status", "active"), "links": json.dumps(links),
        "summary": content[:300],
    }

def rebuild_memory_md(project: str) -> Path:
    d = ensure_project(project)
    notes = sorted((d / "notes").glob("*.md")) + sorted((d / "decisions").glob("*.md"))
    recent = []
    for f in notes[-5:]:
        fm, _ = parse_frontmatter(f.read_text(encoding="utf-8"))
        recent.append(f"- [[{f.stem}]] · {fm.get('title', f.stem)}")
    decisions = [f"- [[{f.stem}]]" for f in (d / "decisions").glob("*.md")]
    sessions = sorted((d / "sessions").glob("*.md"), reverse=True)[:3]
    session_lines = [f"- [[{f.stem}]]" for f in sessions]
    lines = [
        f"# MEMORY INDEX · {project}",
        "",
        "> Este archivo es SOLO un indice. El detalle vive en las notas enlazadas.",
        "",
        "## Objetivo",
        "- (define el objetivo actual del proyecto)",
        "",
        "## Decisiones clave",
    ]
    lines += decisions if decisions else ["- (sin decisiones registradas aun)"]
    lines += ["", "## Notas recientes"]
    lines += recent if recent else ["- (sin notas aun)"]
    lines += ["", "## Sesiones recientes"]
    lines += session_lines if session_lines else ["- (sin sesiones aun)"]
    lines += ["", "## Enlaces",
        f"- Boveda central: `{VAULT_ROOT / project}`",
        "- Abre Obsidian en esa ruta para ver el grafo completo.",
    ]
    mem = d / "MEMORY.md"
    mem.write_text("\n".join(lines), encoding="utf-8")
    return mem

def add_note_index(conn, idx: dict):
    conn.execute("""INSERT OR REPLACE INTO notes_index
        (id, path, title, type, project, tags, created, status, links, summary)
        VALUES (:id,:path,:title,:type,:project,:tags,:created,:status,:links,:summary)""", idx)
    conn.execute("INSERT OR REPLACE INTO notes_fts(id, title, body) VALUES (?,?,?)",
                 (idx["id"], idx["title"], idx["summary"]))

def update_graph_from_note(conn, project: str, idx: dict):
    nid = idx["id"]
    conn.execute("""INSERT OR REPLACE INTO graph_nodes (id,label,type,project,properties)
        VALUES (?,?,?,?,?)""", (nid, idx["title"], idx["type"], project, idx["summary"]))
    try:
        links = json.loads(idx["links"])
    except Exception:
        links = []
    for target in links:
        conn.execute("""INSERT OR REPLACE INTO graph_edges (source,target,relation,project)
            VALUES (?,?,?,?)""", (nid, target, "links", project))
        conn.execute("""INSERT OR REPLACE INTO graph_nodes (id,label,type,project,properties)
            VALUES (?,?,?,?,?)""", (target, target, "note", project, ""))

def export_graph(project: str) -> dict:
    conn = dbs()
    try:
        nodes = [dict(r) for r in conn.execute(
            "SELECT id,label,type,project,properties FROM graph_nodes WHERE project=? ORDER BY id", (project,))]
        edges = [dict(r) for r in conn.execute(
            "SELECT source,target,relation,project FROM graph_edges WHERE project=? ORDER BY source", (project,))]
    finally:
        conn.close()
    return {"project": project, "generated": now_iso(), "nodes": nodes, "edges": edges}

def write_graph_json(project: str):
    d = ensure_project(project)
    data = export_graph(project)
    (d / "graph.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data["nodes"]), len(data["edges"])

def _detect_project(explicit: str = "") -> str:
    p = (explicit or os.environ.get("MEMORY_PROJECT") or "").strip()
    if p:
        return safe_project(p)
    cwd = Path.cwd()
    looks_like_project = (
        (cwd / ".git").exists()
        or any((cwd / f).exists() for f in ("package.json", "pyproject.toml", "requirements.txt",
                                             "Cargo.toml", "go.mod", "wrangler.toml", ".wrangler"))
    )
    if looks_like_project:
        return safe_project(cwd.name)
    return "global"

def tool_init(project: str = "", project_root: str = ""):
    proj = _detect_project(project)
    db_init()
    for sub in ("global", proj):
        ensure_project(sub)
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    PREF_DIR.mkdir(parents=True, exist_ok=True)
    if not IDENTITY_PATH.exists():
        IDENTITY_PATH.write_text(DEFAULT_IDENTITY, encoding="utf-8")
    mem = rebuild_memory_md(proj)
    if project_root:
        root = Path(project_root)
        try:
            root.mkdir(parents=True, exist_ok=True)
            light = [
                f"# MEMORY · {proj}",
                "",
                f"> Indice ligero. La boveda central de Atlas vive en: `{VAULT_ROOT / proj}`",
                "> Abre Obsidian ahi para notas, decisiones, sesiones y grafo.",
                "",
                "Estado del proyecto, decisiones y sesiones recientes: ver boveda central.",
            ]
            (root / "MEMORY.md").write_text("\n".join(light), encoding="utf-8")
            repo_index = f"escrito MEMORY.md en {root}"
        except Exception as e:
            repo_index = f"no se pudo escribir MEMORY.md en project_root: {e}"
    else:
        repo_index = "project_root no proporcionado (solo boveda central)"
    return json.dumps({"success": True, "project": proj, "vault": str(VAULT_ROOT / proj),
                       "db": str(DB_PATH), "identity": str(IDENTITY_PATH),
                       "repo_memory": repo_index}, ensure_ascii=False, indent=2)

def tool_note_save(title: str, body: str, type: str = "fact", project: str = "",
                   tags: str = "", status: str = "active", links: str = ""):
    if type not in NOTE_TYPES:
        return json.dumps({"error": f"tipo invalido: {type}. Usa uno de: {', '.join(NOTE_TYPES)}"})
    proj = _detect_project(project)
    d = ensure_project(proj)
    folder = "decisions" if type == "decision" else ("facts" if type == "fact" else ("preferences" if type == "preference" else "notes"))
    body = redact(body)
    nid = f"{datetime.now():%Y%m%d-%H%M%S}-{slugify(title)[:40]}"
    links_lines = "".join(f"  - \"[[{l.strip()}]]\"\n" for l in (links.split(",") if links else []))
    fm = (
        f"---\nid: {nid}\ntype: {type}\nproject: {proj}\ntags: [{tags}]\n"
        f"created: {now_iso()}\nsource: opencode\nstatus: {status}\n"
        f"links:\n{links_lines}---\n\n"
    )
    path = d / folder / f"{nid}.md"
    path.write_text(fm + body + "\n", encoding="utf-8")
    conn = dbs()
    try:
        idx = note_to_index(path, proj)
        add_note_index(conn, idx)
        update_graph_from_note(conn, proj, idx)
        conn.commit()
        nn, ne = write_graph_json(proj)
    finally:
        conn.close()
    rebuild_memory_md(proj)
    return json.dumps({"success": True, "id": nid, "path": str(path), "graph": {"nodes": nn, "edges": ne}},
                      ensure_ascii=False)

def tool_note_search(query: str, project: str = "", limit: int = 8, scope: str = "project"):
    conn = dbs()
    try:
        rows = []
        if scope in ("project", "both"):
            proj = _detect_project(project)
            rows += [dict(r) for r in conn.execute(
                "SELECT notes_index.id,notes_index.title,notes_index.type,notes_index.project,notes_index.summary "
                "FROM notes_fts JOIN notes_index USING(id) WHERE notes_fts MATCH ? AND notes_index.project=? LIMIT ?",
                (query, proj, limit))]
        if scope in ("global", "both") and not rows:
            rows += [dict(r) for r in conn.execute(
                "SELECT notes_index.id,notes_index.title,notes_index.type,notes_index.project,notes_index.summary "
                "FROM notes_fts JOIN notes_index USING(id) WHERE notes_fts MATCH ? AND notes_index.project='global' LIMIT ?",
                (query, limit))]
    finally:
        conn.close()
    return json.dumps({"count": len(rows), "results": rows}, ensure_ascii=False, indent=2)

def tool_session_start(project: str = "", note: str = ""):
    proj = _detect_project(project)
    ensure_project(proj)
    sid = f"sesion-{datetime.now():%Y%m%d-%H%M%S}"
    conn = dbs()
    try:
        conn.execute("INSERT INTO sessions (id,project,started,status,summary) VALUES (?,?,?,?,?)",
                     (sid, proj, now_iso(), "active", note))
        conn.commit()
    finally:
        conn.close()
    return json.dumps({"success": True, "session_id": sid, "project": proj, "started": now_iso()}, ensure_ascii=False)

def tool_session_end(session_id: str = "", summary: str = "", project: str = ""):
    conn = dbs()
    try:
        if session_id:
            row = conn.execute("SELECT * FROM sessions WHERE id=? AND status='active'", (session_id,)).fetchone()
        elif project:
            proj = _detect_project(project)
            row = conn.execute("SELECT * FROM sessions WHERE status='active' AND project=? ORDER BY started DESC LIMIT 1", (proj,)).fetchone()
        else:
            row = conn.execute("SELECT * FROM sessions WHERE status='active' ORDER BY started DESC LIMIT 1").fetchone()
        if not row:
            return json.dumps({"error": "no hay sesion activa (usa memory_session_start o --cli session_recover)"})
        summary = redact(summary) if summary else "Sesion cerrada (resumen no proporcionado)."
        conn.execute("UPDATE sessions SET ended=?, status='ended', summary=? WHERE id=?",
                     (now_iso(), summary, row["id"]))
        conn.commit()
        sid = row["id"]; proj = row["project"]
    finally:
        conn.close()
    d = ensure_project(proj)
    path = d / "sessions" / f"{sid}.md"
    path.write_text(f"---\nid: {sid}\ntype: session\nproject: {proj}\ncreated: {now_iso()}\nstatus: ended\n---\n\n{summary}\n", encoding="utf-8")
    conn = dbs()
    try:
        add_note_index(conn, note_to_index(path, proj))
        conn.commit()
    finally:
        conn.close()
    rebuild_memory_md(proj)
    return json.dumps({"success": True, "session_id": sid, "ended": now_iso(), "summary": summary[:200]}, ensure_ascii=False)

def tool_session_recover(project: str = ""):
    conn = dbs()
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT id,project,started FROM sessions WHERE status='active' ORDER BY started")]
        for r in rows:
            conn.execute("UPDATE sessions SET status='recovered', ended=?, summary='Sesion huerfana recuperada al reiniciar.' WHERE id=?",
                         (now_iso(), r["id"]))
        conn.commit()
    finally:
        conn.close()
    return json.dumps({"success": True, "recovered": len(rows), "sessions": rows}, ensure_ascii=False)

def tool_event_ingest(project: str = ""):
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    conn = dbs()
    ingested = 0; errors = []
    try:
        for f in sorted(INBOX_DIR.glob("*.jsonl")):
            try:
                for line in f.read_text(encoding="utf-8-sig").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    ev = json.loads(line)
                    ev["payload"] = redact(json.dumps(ev.get("data", {}), ensure_ascii=False))
                    eid = ev.get("id") or f"evt_{uuid.uuid4().hex[:12]}"
                    conn.execute("""INSERT OR REPLACE INTO events
                        (id,ts,source,type,project,app,window_title,category,monetizable,risk,duration_seconds,payload)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
                        eid, ev.get("ts", now_iso()), ev.get("source", "inbox"),
                        ev.get("type", "generic"), ev.get("project") or _detect_project(project),
                        ev.get("app"), ev.get("window_title"), ev.get("category"),
                        1 if ev.get("monetizable") else 0, ev.get("risk"),
                        ev.get("duration_seconds"), ev["payload"]))
                    ingested += 1
                f.unlink()
            except Exception as e:
                errors.append(f"{f.name}: {e}")
        conn.commit()
    finally:
        conn.close()
    return json.dumps({"success": True, "ingested": ingested, "errors": errors}, ensure_ascii=False)

def tool_pref_set(key: str, value: str, project: str = ""):
    proj = _detect_project(project)
    scope = "global" if proj == "global" else "project"
    value = redact(value)
    conn = dbs()
    try:
        conn.execute("INSERT OR REPLACE INTO preferences (key,value,scope,project,updated) VALUES (?,?,?,?,?)",
                     (key, value, scope, proj, now_iso()))
        conn.commit()
    finally:
        conn.close()
    d = ensure_project("global" if scope == "global" else proj)
    p = d / "preferences" / f"{key}.md"
    p.write_text(f"---\ntype: preference\nproject: {proj}\nupdated: {now_iso()}\n---\n\n# {key}\n\n{value}\n", encoding="utf-8")
    return json.dumps({"success": True, "key": key, "scope": scope, "project": proj}, ensure_ascii=False)

def tool_pref_get(key: str = "", project: str = ""):
    conn = dbs()
    try:
        if key:
            proj = _detect_project(project)
            rows = [dict(r) for r in conn.execute("SELECT * FROM preferences WHERE key=? AND (project=? OR project='global')",
                                                  (key, proj))]
        else:
            rows = [dict(r) for r in conn.execute("SELECT * FROM preferences ORDER BY scope,project,key")]
    finally:
        conn.close()
    return json.dumps({"count": len(rows), "preferences": rows}, ensure_ascii=False, indent=2)

def tool_graph_query(node: str = "", project: str = "", depth: int = 2):
    proj = _detect_project(project)
    conn = dbs()
    try:
        if node:
            visited, frontier = set(), {node}
            for _ in range(max(1, min(depth, 5))):
                nxt = set()
                for src, tgt in conn.execute(
                        "SELECT source,target FROM graph_edges WHERE project=? AND (source=? OR target=?)", (proj, node, node)):
                    nxt.add(tgt if src == node else src)
                frontier = nxt - visited
                visited |= frontier
                if not frontier:
                    break
            related = sorted(visited)
        else:
            related = [r["id"] for r in conn.execute("SELECT id FROM graph_nodes WHERE project=? ORDER BY id", (proj,))]
        if related:
            ph = ",".join("?" * len(related))
            nodes = [dict(r) for r in conn.execute(
                f"SELECT id,label,type FROM graph_nodes WHERE id IN ({ph}) AND project=?", (*related, proj))]
            edges = [dict(r) for r in conn.execute(
                f"SELECT source,target,relation FROM graph_edges WHERE project=? AND (source IN ({ph}) OR target IN ({ph}))", (proj, *related, *related))]
        else:
            nodes, edges = [], []
    finally:
        conn.close()
    return json.dumps({"project": proj, "query": node, "nodes": len(nodes), "edges": len(edges),
                       "node_list": nodes, "edge_list": edges}, ensure_ascii=False, indent=2)

def tool_graph_rebuild(project: str = ""):
    proj = _detect_project(project)
    d = ensure_project(proj)
    conn = dbs()
    try:
        conn.execute("DELETE FROM graph_nodes WHERE project=?", (proj,))
        conn.execute("DELETE FROM graph_edges WHERE project=?", (proj,))
        for f in list((d / "notes").glob("*.md")) + list((d / "decisions").glob("*.md")) + list((d / "sessions").glob("*.md")):
            idx = note_to_index(f, proj)
            if idx:
                update_graph_from_note(conn, proj, idx)
        conn.commit()
        nn, ne = write_graph_json(proj)
    finally:
        conn.close()
    return json.dumps({"success": True, "project": proj, "nodes": nn, "edges": ne}, ensure_ascii=False)

def tool_summary(project: str = "", budget: int = 2500):
    proj = _detect_project(project)
    conn = dbs()
    parts = []
    try:
        ident = IDENTITY_PATH.read_text(encoding="utf-8") if IDENTITY_PATH.exists() else DEFAULT_IDENTITY
        _, ident_body = parse_frontmatter(ident)
        parts.append("## Identidad de Atlas (global)\n" + ident_body.strip()[:400])
        prefs = [r for r in conn.execute("SELECT key,value,scope FROM preferences ORDER BY scope,key")]
        if prefs:
            lines = "\n".join(f"- {r['key']}: {r['value'][:120]}" for r in prefs[:10])
            parts.append("## Preferencias\n" + lines)
        mem = ensure_project(proj) / "MEMORY.md"
        if mem.exists():
            parts.append("## Estado del proyecto\n" + mem.read_text(encoding="utf-8")[:1200])
        ses = [dict(r) for r in conn.execute(
            "SELECT id,project,started,ended,status,substr(summary,1,120) s FROM sessions WHERE project=? ORDER BY started DESC LIMIT 3", (proj,))]
        if ses:
            parts.append("## Sesiones recientes\n" + "\n".join(
                f"- {r['id']} [{r['status']}] {r['started']}: {r['s']}" for r in ses))
        dec = [dict(r) for r in conn.execute(
            "SELECT id,title,summary FROM notes_index WHERE project=? AND type='decision' AND status='active' ORDER BY created DESC LIMIT 5", (proj,))]
        if dec:
            parts.append("## Decisiones abiertas\n" + "\n".join(f"- [[{r['id']}]] {r['title']}: {r['summary'][:100]}" for r in dec))
        tareas = [dict(r) for r in conn.execute(
            "SELECT id,title,summary FROM notes_index WHERE project=? AND type='task' AND status='active' ORDER BY created DESC LIMIT 5", (proj,))]
        if tareas:
            parts.append("## Tareas pendientes\n" + "\n".join(f"- [[{r['id']}]] {r['title']}: {r['summary'][:100]}" for r in tareas))
        ev = [dict(r) for r in conn.execute(
            "SELECT ts,type,app,category,monetizable,duration_seconds FROM events WHERE project=? ORDER BY ts DESC LIMIT 6", (proj,))]
        if ev:
            parts.append("## Eventos recientes\n" + "\n".join(
                f"- {r['ts']} {r['type']} app={r['app']} cat={r['category']} $={r['monetizable']} dur={r['duration_seconds']}" for r in ev))
    finally:
        conn.close()
    text = "\n\n".join(parts)
    if budget and len(text) > budget:
        text = text[:budget] + "\n...[resumen truncado por presupuesto de tokens]"
    return json.dumps({"project": proj, "tokens_approx": len(text) // 4, "context": text}, ensure_ascii=False, indent=2)

def read_daemon_heartbeat() -> dict:
    """Lee state/daemon.heartbeat (F2) y devuelve estado del daemon de actividad."""
    hb_file = STATE_DIR / "daemon.heartbeat"
    if not hb_file.exists():
        return {"daemon": "down", "reason": "sin heartbeat (atlas_activity.py no corre)"}
    try:
        hb = json.loads(hb_file.read_text(encoding="utf-8"))
        last = datetime.fromisoformat(hb.get("last_tick", "2000-01-01T00:00:00+00:00"))
        age = (datetime.now(timezone.utc) - last).total_seconds()
        status = hb.get("status", "unknown")
        if status == "stopped":
            return {"daemon": "stopped", "last_tick": hb.get("last_tick"), "age_seconds": int(age)}
        if age > 120:
            return {"daemon": "down", "last_tick": hb.get("last_tick"), "age_seconds": int(age),
                    "pid": hb.get("pid")}
        return {"daemon": "up", "status": status, "paused": bool(hb.get("paused")),
                "last_tick": hb.get("last_tick"), "age_seconds": int(age),
                "pid": hb.get("pid"), "ticks": hb.get("ticks", 0)}
    except Exception as e:
        return {"daemon": "error", "reason": str(e)}

SECRET_ROTATION_FILE = STATE_DIR / "secret_rotation.json"
SECRET_ROTATION_DAYS = 90

def read_secret_rotation() -> dict:
    """Estado de rotacion de secretos: ultima rotacion + proxima fecha."""
    if not SECRET_ROTATION_FILE.exists():
        return {
            "last_rotated": None,
            "next_due": None,
            "due": True,
            "days_remaining": 0,
            "note": "nunca rotado: registrar la primera rotacion",
        }
    try:
        data = json.loads(SECRET_ROTATION_FILE.read_text(encoding="utf-8"))
        last = datetime.fromisoformat(data.get("last_rotated", "2000-01-01T00:00:00+00:00"))
        next_due = data.get("next_due")
        if next_due:
            next_dt = datetime.fromisoformat(next_due)
        else:
            next_dt = last + timedelta(days=SECRET_ROTATION_DAYS)
        days_remaining = int((next_dt - datetime.now(timezone.utc)).total_seconds() / 86400)
        return {
            "last_rotated": data.get("last_rotated"),
            "next_due": next_dt.isoformat(timespec="seconds"),
            "due": days_remaining <= 0,
            "days_remaining": days_remaining,
            "note": data.get("note", ""),
        }
    except Exception:
        return {"last_rotated": None, "next_due": None, "due": True,
                "days_remaining": 0, "note": "archivo de rotacion corrupto"}

def mark_secret_rotation(note: str = "") -> dict:
    """Registra una rotacion de secretos (para el calendario de 90 dias)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    last = datetime.now(timezone.utc).isoformat(timespec="seconds")
    next_due = (datetime.now(timezone.utc) + timedelta(days=SECRET_ROTATION_DAYS)).isoformat(timespec="seconds")
    data = {
        "last_rotated": last,
        "next_due": next_due,
        "note": note or "rotacion de secretos registrada",
    }
    SECRET_ROTATION_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return read_secret_rotation()

def tool_health():
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    backlog = len(list(INBOX_DIR.glob("*.jsonl")))
    conn = dbs()
    try:
        orphan = conn.execute("SELECT COUNT(*) c FROM sessions WHERE status='active'").fetchone()["c"]
        n_notes = conn.execute("SELECT COUNT(*) c FROM notes_index").fetchone()["c"]
        n_events = conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        graphs = sorted(VAULT_ROOT.glob("*/graph.json"))
    finally:
        conn.close()
    daemon = read_daemon_heartbeat()
    # monitoreo de errores (atlas_monitor)
    try:
        from atlas_monitor import recent_errors
        errs = recent_errors()
    except Exception:
        errs = []
    # calendario de rotacion de secretos (90 dias)
    rotation = read_secret_rotation()
    issues = []
    if backlog > 0: issues.append(f"inbox pendiente de procesar: {backlog}")
    if orphan > 0: issues.append(f"sesiones huerfanas activas: {orphan} (correr memory_session_recover)")
    if integrity != "ok": issues.append(f"integridad DB: {integrity}")
    if daemon.get("daemon") == "down":
        issues.append(f"daemon de actividad abajo ({daemon.get('reason', 'sin heartbeat')})")
    err_total = sum(e["count"] for e in errs)
    if err_total > 0: issues.append(f"{err_total} error(es) en las ultimas 24h (ver logs/errors.jsonl)")
    if rotation.get("due"):
        issues.append("secretos pendientes de rotacion (calendario 90 dias)")
    status = "ok" if not issues else "attention"
    return json.dumps({
        "status": status, "db_integrity": integrity,
        "notes": n_notes, "events": n_events, "orphan_sessions": orphan,
        "inbox_backlog": backlog, "graphs": [str(g) for g in graphs],
        "daemon": daemon, "errors_24h": errs, "error_total_24h": err_total,
        "secret_rotation": rotation, "issues": issues, "vault": str(VAULT_ROOT)}, ensure_ascii=False, indent=2)

def tool_gc(keep_days: int = 90):
    cutoff = (datetime.now(timezone.utc).timestamp() - keep_days * 86400)
    cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat(timespec="seconds")
    conn = dbs()
    try:
        cur = conn.execute("DELETE FROM events WHERE ts < ?", (cutoff_iso,))
        del_events = cur.rowcount
        cur = conn.execute("UPDATE sessions SET status='archived' WHERE status IN ('ended','recovered') AND started < ?", (cutoff_iso,))
        del_ses = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return json.dumps({"success": True, "events_deleted": del_events, "sessions_archived": del_ses}, ensure_ascii=False)

def tool_projects(limit: int = 20):
    """Resumen de TODOS los proyectos con memoria (para abrir Atlas desde fuera de un proyecto)."""
    conn = dbs()
    projects = []
    try:
        for d in sorted(VAULT_ROOT.glob("*/")):
            name = d.name
            if name in ("global", "inbox") or not d.is_dir():
                continue
            stats = {"name": name, "vault": str(d)}
            stats["notes"] = sum(1 for _ in (d / "notes").glob("*.md")) if (d / "notes").exists() else 0
            stats["decisions"] = sum(1 for _ in (d / "decisions").glob("*.md")) if (d / "decisions").exists() else 0
            sessions = sorted((d / "sessions").glob("*.md"), reverse=True) if (d / "sessions").exists() else []
            stats["sessions"] = len(sessions)
            if sessions:
                fm, body = parse_frontmatter(sessions[0].read_text(encoding="utf-8"))
                stats["last_session"] = fm.get("created", "")
                stats["last_session_summary"] = body.strip()[:200]
            else:
                stats["last_session"] = ""
                stats["last_session_summary"] = ""
            row = conn.execute("SELECT value FROM preferences WHERE key='objetivo' AND project=? LIMIT 1",
                               (name,)).fetchone()
            if row:
                stats["objective"] = row["value"][:200]
            else:
                mem = d / "MEMORY.md"
                if mem.exists():
                    _, body = parse_frontmatter(mem.read_text(encoding="utf-8"))
                    obj = ""
                    if "## Objetivo" in body:
                        obj = body.split("## Objetivo", 1)[1].split("##", 1)[0].strip()
                    stats["objective"] = obj[:200] if obj else body.strip()[:200]
            projects.append(stats)
    finally:
        conn.close()
    projects.sort(key=lambda p: p.get("last_session", ""), reverse=True)
    return json.dumps({"count": len(projects), "projects": projects[:limit]}, ensure_ascii=False, indent=2)

def tool_publish_report(html_path, title="", level="L2", note_body=""):
    """Publica un informe (REQ-C8): copia HTML a vault/outputs/, indexa en
    state/reports_index.json y crea nota MD de respaldo."""
    try:
        from pathlib import Path as _Path
        import shutil as _shutil

        outputs = _Path(VAULT_ROOT) / "outputs"
        outputs.mkdir(parents=True, exist_ok=True)

        html = _Path(html_path)
        if not html.exists():
            return json.dumps({"error": f"archivo no existe: {html_path}"}, ensure_ascii=False)

        safe_title = re.sub(r"[^A-Za-z0-9 _-]", "", title or html.stem).strip().replace(" ", "_")
        if not safe_title:
            safe_title = "informe"
        version = "v1"
        dest = outputs / f"{safe_title}-{version}.html"
        n = 1
        while dest.exists():
            n += 1
            version = f"v{n}"
            dest = outputs / f"{safe_title}-{version}.html"

        _shutil.copy2(str(html), str(dest))

        now = datetime.now()
        entry = {
            "id": f"{now.strftime('%Y%m%d_%H%M%S')}-{safe_title}",
            "title": title or html.stem,
            "level": level,
            "path": str(dest),
            "url": f"/informe/{dest.name}",
            "published": now.isoformat(),
            "version": version,
        }
        index_file = STATE_DIR / "reports_index.json"
        index = []
        if index_file.exists():
            try:
                index = json.loads(index_file.read_text(encoding="utf-8"))
            except Exception:
                index = []
        index.append(entry)
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

        note_file = _Path(VAULT_ROOT) / "global" / "notes" / f"{now.strftime('%Y%m%d-%H%M%S')}-{safe_title}.md"
        note_file.parent.mkdir(parents=True, exist_ok=True)
        note_file.write_text(
            f"---\ntype: delivery\ntitle: {title or html.stem}\nlevel: {level}\n"
            f"path: {dest}\ndate: {now.isoformat()}\n---\n\n"
            f"{note_body or 'Informe publicado en outputs/'}\n\nFuente: [[{dest.name}]]\n",
            encoding="utf-8",
        )

        return json.dumps({"success": True, "path": str(dest), "id": entry["id"],
                           "url": entry["url"]}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

def tool_backup(keep: int = 14):
    """Crea un zip de vault+DB y deja solo los `keep` mas recientes."""
    BACKUP_DIR = MEMORY_ROOT / "backup"
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    # checkpoint WAL para que el zip contenga la DB coherente
    if DB_PATH.exists():
        try:
            conn = db_connect()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.close()
        except Exception:
            pass
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zpath = BACKUP_DIR / f"atlas_{ts}.zip"
    with zipfile.ZipFile(str(zpath), "w", zipfile.ZIP_DEFLATED) as zf:
        # vault completo
        for root, dirs, files in os.walk(str(VAULT_ROOT)):
            for fn in files:
                fp = Path(root) / fn
                zf.write(str(fp), f"vault/{fp.relative_to(VAULT_ROOT)}")
        # state/ (DB)
        for fp in STATE_DIR.glob("memory.db*"):
            zf.write(str(fp), f"state/{fp.name}")
    backups = sorted(BACKUP_DIR.glob("atlas_*.zip"))
    deleted = []
    while len(backups) > keep:
        old = backups.pop(0)
        old.unlink()
        deleted.append(old.name)
    return json.dumps({"success": True, "backup": str(zpath), "kept": len(backups), "deleted": deleted,
                       "size_bytes": zpath.stat().st_size}, ensure_ascii=False)

def tool_restore(backup_file: str = ""):
    """Si no se da ruta, lista backups. Si se da, restaura."""
    BACKUP_DIR = MEMORY_ROOT / "backup"
    if not backup_file:
        backups = sorted(BACKUP_DIR.glob("atlas_*.zip"), reverse=True)
        items = [{"name": b.name, "size_bytes": b.stat().st_size,
                  "created": datetime.fromtimestamp(b.stat().st_mtime, tz=timezone.utc).isoformat()} for b in backups]
        return json.dumps({"available": len(items), "backups": items}, ensure_ascii=False, indent=2)
    src = Path(backup_file) if Path(backup_file).is_absolute() else BACKUP_DIR / backup_file
    if not src.exists():
        return json.dumps({"error": f"backup no encontrado: {src}"})
    # restaurar
    with zipfile.ZipFile(str(src), "r") as zf:
        zf.extractall(str(MEMORY_ROOT))
    return json.dumps({"success": True, "restored_from": str(src), "vault": str(VAULT_ROOT), "db": str(DB_PATH)})

def cli_hook_event(payload_json: str):
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    try:
        ev = json.loads(payload_json)
    except Exception as e:
        return json.dumps({"error": f"payload no es JSON valido: {e}"})
    ev.setdefault("id", f"evt_{uuid.uuid4().hex[:12]}")
    ev.setdefault("ts", now_iso())
    ev.setdefault("source", "git-hook")
    f = INBOX_DIR / f"git-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.jsonl"
    f.write_text(json.dumps(ev, ensure_ascii=False) + "\n", encoding="utf-8")
    return json.dumps({"success": True, "inbox": str(f)}, ensure_ascii=False)

def cli_git_event(project: str, hash: str, message: str, files: str = ""):
    """Modo para hooks: recibe campos por separado (sin JSON), robusto a quoting."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    ev = {
        "id": f"evt_{uuid.uuid4().hex[:12]}",
        "ts": now_iso(),
        "source": "git-hook",
        "type": "commit",
        "project": safe_project(project),
        "data": {"hash": hash, "message": message[:200],
                 "files": [f.strip() for f in files.split(",") if f.strip()]},
    }
    f = INBOX_DIR / f"git-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.jsonl"
    f.write_text(json.dumps(ev, ensure_ascii=False) + "\n", encoding="utf-8")
    return json.dumps({"success": True, "inbox": str(f)}, ensure_ascii=False)

def cli_dispatch(cmd: str, args: dict):
    if cmd == "init": return tool_init(**args)
    if cmd == "note_save": return tool_note_save(**args)
    if cmd == "note_search": return tool_note_search(**args)
    if cmd == "session_start": return tool_session_start(**args)
    if cmd == "session_end": return tool_session_end(**args)
    if cmd == "session_recover": return tool_session_recover(**args)
    if cmd == "event_ingest": return tool_event_ingest(**args)
    if cmd == "pref_set": return tool_pref_set(**args)
    if cmd == "pref_get": return tool_pref_get(**args)
    if cmd == "graph_query": return tool_graph_query(**args)
    if cmd == "graph_rebuild": return tool_graph_rebuild(**args)
    if cmd == "summary": return tool_summary(**args)
    if cmd == "health": return tool_health()
    if cmd == "gc": return tool_gc(**args)
    if cmd == "projects": return tool_projects(**args)
    if cmd == "backup": return tool_backup(**args)
    if cmd == "restore": return tool_restore(**args)
    if cmd == "secret_rotation": return json.dumps(mark_secret_rotation(note=args.get("note", "")))
    if cmd == "rotate_secrets": return json.dumps(mark_secret_rotation(note=args.get("note", "")))
    return json.dumps({"error": f"comando CLI desconocido: {cmd}"})

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--hook-env":
        # Robustez ante quoting del mensaje: los datos llegan por env vars
        # (asignacion literal en sh, no re-interpretada), no por argv.
        print(cli_git_event(
            os.environ.get("ATLAS_GIT_PROJECT", "global"),
            os.environ.get("ATLAS_GIT_HASH", ""),
            os.environ.get("ATLAS_GIT_MSG", ""),
            os.environ.get("ATLAS_GIT_FILES", ""),
        ))
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "--hook-event":
        print(cli_hook_event(sys.argv[2]))
        return
    if len(sys.argv) >= 5 and sys.argv[1] == "--git":
        # --git <proyecto> <hash> <mensaje> [files_csv]
        files = sys.argv[5] if len(sys.argv) >= 6 else ""
        print(cli_git_event(sys.argv[2], sys.argv[3], sys.argv[4], files))
        return
    if len(sys.argv) >= 3 and sys.argv[1] == "--cli":
        cmd = sys.argv[2]
        args = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i].startswith("--"):
                k = sys.argv[i][2:].replace("-", "_")
                v = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
                if v.lower() == "true": v = True
                elif v.lower() == "false": v = False
                else:
                    try: v = int(v)
                    except ValueError:
                        try: v = float(v)
                        except ValueError: pass
                args[k] = v
                i += 2
            else:
                if "project" not in args:
                    args["project"] = sys.argv[i]
                i += 1
        print(cli_dispatch(cmd, args))
        return
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("Atlas Memory Server")

    @mcp.tool()
    def memory_init(project: str = "", project_root: str = "") -> str:
        """Inicializa la boveda/memoria del proyecto (global o especifico). Opcional: project_root para escribir el MEMORY.md hibrido en el repo."""
        return tool_init(project, project_root)

    @mcp.tool()
    def memory_note_save(title: str, body: str, type: str = "fact", project: str = "",
                         tags: str = "", status: str = "active", links: str = "") -> str:
        """Guarda una nota Obsidian con frontmatter. type: decision|fact|preference|summary|opportunity|task|risk|lesson|session. links separados por coma como [[nota]]."""
        return tool_note_save(title, body, type, project, tags, status, links)

    @mcp.tool()
    def memory_note_search(query: str, project: str = "", limit: int = 8, scope: str = "project") -> str:
        """Busca notas por texto (FTS5) en el proyecto (scope=project) o global."""
        return tool_note_search(query, project, limit, scope)

    @mcp.tool()
    def memory_session_start(project: str = "", note: str = "") -> str:
        """Inicia una sesion de trabajo (detecta proyecto actual)."""
        return tool_session_start(project, note)

    @mcp.tool()
    def memory_session_end(session_id: str = "", summary: str = "") -> str:
        """Cierra la sesion activa y genera nota de sesion. Si no pasas session_id cierra la mas reciente."""
        return tool_session_end(session_id, summary)

    @mcp.tool()
    def memory_session_recover(project: str = "") -> str:
        """Detecta sesiones activas huerfanas (sesion no cerrada) y las marca recovered."""
        return tool_session_recover(project)

    @mcp.tool()
    def memory_event_ingest(project: str = "") -> str:
        """Drena los eventos de inbox/ (git hooks, futuros daemons) a SQLite. Correr despues de un commit."""
        return tool_event_ingest(project)

    @mcp.tool()
    def memory_pref_set(key: str, value: str, project: str = "") -> str:
        """Guarda una preferencia (scope global si project='global', si no scope del proyecto)."""
        return tool_pref_set(key, value, project)

    @mcp.tool()
    def memory_pref_get(key: str = "", project: str = "") -> str:
        """Lee preferencias (una clave o todas)."""
        return tool_pref_get(key, project)

    @mcp.tool()
    def memory_graph_query(node: str = "", project: str = "", depth: int = 2) -> str:
        """Consulta el grafo de conocimiento: vecinos de un nodo o lista completa."""
        return tool_graph_query(node, project, depth)

    @mcp.tool()
    def memory_graph_rebuild(project: str = "") -> str:
        """Reconstruye el grafo derivado desde notas (frontmatter + wikilinks). Confirmar antes de usar."""
        return tool_graph_rebuild(project)

    @mcp.tool()
    def memory_summary(project: str = "", budget: int = 2500) -> str:
        """Devuelve contexto compacto (identidad, estado, sesiones, decisiones, pendientes, eventos) con presupuesto de tokens."""
        return tool_summary(project, budget)

    @mcp.tool()
    def memory_health() -> str:
        """Diagnostico: integridad DB, inbox backlog, sesiones huerfanas, conteos."""
        return tool_health()

    @mcp.tool()
    def memory_gc(keep_days: int = 90) -> str:
        """Limpia eventos viejos y archiva sesiones antiguas (default 90 dias). Confirmar antes de usar."""
        return tool_gc(keep_days)

    @mcp.tool()
    def memory_projects(limit: int = 20) -> str:
        """Resumen de TODOS los proyectos con memoria (usar cuando se abre Atlas fuera de un proyecto, ej. escritorio)."""
        return tool_projects(limit)

    @mcp.tool()
    def memory_publish_report(html_path: str, title: str = "", level: str = "L2", note_body: str = "") -> str:
        """
        Publica un informe/entregable (REQ-C8): copia el HTML a vault/outputs/,
        registra un index en state/reports_index.json (para el dashboard) y
        crea una nota MD de respaldo en la boveda del proyecto.

        Args:
            html_path: ruta del HTML generado (se copia a vault/outputs/)
            title: titulo del informe
            level: nivel L0-L3
            note_body: contenido MD adicional para la nota de respaldo

        Returns:
            JSON con la ruta publicada y el id del informe
        """
        return tool_publish_report(html_path, title, level, note_body)

    mcp.run()

if __name__ == "__main__":
    main()
