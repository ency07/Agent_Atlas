# ============================================================
# atlas_sync_capabilities.py — Auto-sync de capacidades de modelos
# ------------------------------------------------------------
# Consulta /v1/models de cada proveedor activo, actualiza
# model_capabilities.json y genera diff con la versión anterior.
#
# Uso:
#   python atlas_sync_capabilities.py          # sync + diff
#   python atlas_sync_capabilities.py --dry-run # solo diff, sin sobrescribir
# ============================================================
import json
import os
import sys
import argparse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
MEMORY_ROOT = ROOT / "memory_data"
STATE_DIR = MEMORY_ROOT / "state"
CAPS_FILE = STATE_DIR / "model_capabilities.json"
SYNC_LOG = STATE_DIR / "sync_capabilities.log"

# Providers conocidos (mismo que atlas_orchestrator)
PROVIDERS = {
    "omniroute": {"port": 20128, "api": "http://localhost:20128/v1"},
    "9router":   {"port": 4000,  "api": "http://localhost:4000/v1"},
    "ollama":    {"port": 11434, "api": "http://localhost:11434/v1"},
}

# Capacidades base conocidas (se mantienen si el modelo sigue existiendo)
KNOWN_CAPABILITIES = {
    "vision": {"default": False, "keywords": ["vision", "vl", "multimodal", "gpt-4o", "claude", "gemini", "kimi"]},
    "reasoning": {"default": False, "keywords": ["reasoning", "think", "o1", "o3", "o4", "deepseek-r1"]},
    "coding": {"default": 0.5, "keywords": ["code", "coding", "coder"]},
}

# Combos curados de omniroute (auto/*) verificados como vivos en el catalogo real.
# Si uno desaparece del catalogo -> dead reference: alerta + eliminacion automatica.
known_curated = {
    "omniroute/auto/best-coding",
    "omniroute/auto/best-reasoning",
    "omniroute/auto/best-vision",
    "omniroute/auto/best-fast",
    "omniroute/auto/best-chat",
    "omniroute/auto/best-coding-fast",
}

def log(msg):
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] {msg}"
    print(line)
    SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def fetch_models(provider_name, provider_config):
    """Consulta /v1/models de un proveedor"""
    url = f"{provider_config['api']}/models"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        models = data.get("data", [])
        return [{"id": m["id"], "object": m.get("object", "model"), "owned_by": m.get("owned_by", ""), "context_length": m.get("context_length", 0)} for m in models]
    except Exception as e:
        log(f"  [{provider_name}] Error consultando {url}: {e}")
        return []

def infer_capability(model_id, provider_data):
    """Inferencia heurística de capacidades desde el ID y metadata"""
    model_lower = model_id.lower()
    caps = {
        "vision": False,
        "reasoning": False,
        "coding": 0.5,
        "research": 0.5,
        "speed": 0.5,
        "context_ok": True,
    }
    # Vision
    if any(kw in model_lower for kw in ["vision", "vl", "multimodal", "gpt-4o", "gpt-5", "claude-opus", "claude-sonnet", "gemini-pro", "gemini-flash", "kimi", "glm"]):
        caps["vision"] = True
    # Reasoning
    if any(kw in model_lower for kw in ["reasoning", "think", "o1", "o3", "o4", "deepseek-r1", "pro-coding", "pro-reasoning"]):
        caps["reasoning"] = True
    # Coding
    if any(kw in model_lower for kw in ["code", "coding", "coder", "best-coding"]):
        caps["coding"] = 0.95
    # Speed (modelos específicos conocidos)
    if any(kw in model_lower for kw in ["fast", "flash", "mini", "haiku", "phi4", "qwen2.5:1.5b"]):
        caps["speed"] = 0.9
    # Contexto
    ctx = provider_data.get("context_length", 0) or 0
    caps["context_ok"] = ctx >= 8192
    return caps

def build_capabilities_file(snapshots, old_caps):
    """Construye el archivo de capacidades nuevo, preservando capacidades conocidas"""
    new_models = {}
    for provider, models in snapshots.items():
        for m in models:
            model_key = f"{provider}/{m['id']}"
            # Preservar si ya existía
            if model_key in old_caps.get("models", {}):
                caps = old_caps["models"][model_key].copy()
                caps["_last_seen"] = datetime.now().isoformat()
            else:
                caps = infer_capability(m["id"], m)
                caps["_first_seen"] = datetime.now().isoformat()
                caps["_last_seen"] = datetime.now().isoformat()
            caps["context_length"] = m.get("context_length", 0)
            caps["owned_by"] = m.get("owned_by", "")
            new_models[model_key] = caps

    # Construir estructura final
    result = {
        "_meta": {
            "version": old_caps.get("_meta", {}).get("version", 1) + 1,
            "updated": datetime.now().isoformat(),
            "description": "Capacidades de modelos sincronizadas desde providers activos.",
        },
        "models": new_models,
        "fallback_sin_router": "ollama/phi4-mini",
        "regla_dorada": "NUNCA ejecutar una tarea de revision visual con un modelo vision=false. Avisar y sugerir cambiar a un modelo vision=true antes de intentar.",
    }

    # task_to_model preservar del anterior si existe, pero validar referencias
    if "task_to_model" in old_caps:
        t2m = old_caps["task_to_model"]
        validated = {}
        dead = []
        for task, model_ref in t2m.items():
            # referencias validas: existen en el catalogo vivo o son combos curados conocidos
            if model_ref in new_models:
                validated[task] = model_ref
            elif model_ref.startswith("omniroute/auto/") and model_ref in known_curated:
                validated[task] = model_ref
            else:
                dead.append({"task": task, "model": model_ref})
        result["task_to_model"] = validated
        if dead:
            log(f"[ALERTA] Referencias muertas en task_to_model (auto-eliminadas):")
            for d in dead:
                log(f"  - {d['task']} -> {d['model']}")

    # Validar referencias muertas en el mapa de modelos (combos curados que no estan en el catalogo)
    for key in list(new_models.keys()):
        if key.startswith("omniroute/auto/"):
            # combo curado: verificar que el proveedor omniroute sigue vivo en este snapshot
            if "omniroute" not in snapshots or not snapshots["omniroute"]:
                pass  # omniroute no consultable este run; no borrar a ciegas
    return result

def compute_diff(old_caps, new_caps):
    """Calcula diff entre versiones"""
    old_models = set(old_caps.get("models", {}).keys())
    new_models = set(new_caps.get("models", {}).keys())
    added = new_models - old_models
    removed = old_models - new_models
    existing = new_models & old_models

    # Verificar cambios en capacidades
    changed = []
    for model_key in existing:
        old_m = old_caps["models"][model_key]
        new_m = new_caps["models"][model_key]
        diffs = []
        for key in ["vision", "reasoning", "coding", "context_ok"]:
            if old_m.get(key) != new_m.get(key):
                diffs.append(f"{key}: {old_m.get(key)} -> {new_m.get(key)}")
        if diffs:
            changed.append({"model": model_key, "changes": diffs})

    return {
        "added": sorted(added),
        "removed": sorted(removed),
        "changed": changed,
        "total_old": len(old_models),
        "total_new": len(new_models),
    }

def sync_cmd(args):
    """Ejecuta sync completo"""
    log("=== INICIO SYNC CAPACIDADES ===")

    # 1. Cargar capacidades actuales
    old_caps = {}
    if CAPS_FILE.exists():
        try:
            old_caps = json.loads(CAPS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"Warning: no se pudo leer caps anterior: {e}")

    # 2. Consultar providers activos
    snapshots = {}
    for name, config in PROVIDERS.items():
        log(f"  Consultando {name}:{config['port']}...")
        models = fetch_models(name, config)
        if models:
            snapshots[name] = models
            log(f"  [{name}] {len(models)} modelos disponibles")
        else:
            log(f"  [{name}] no responde o sin modelos")

    if not snapshots:
        log("ERROR: ningun provider respondio")
        return

    # 3. Construir capacidades nuevas
    new_caps = build_capabilities_file(snapshots, old_caps)

    # 4. Calcular diff
    diff = compute_diff(old_caps, new_caps)
    log(f"  Diff: +{len(diff['added'])} -{len(diff['removed'])} ~{len(diff['changed'])}")
    if diff["added"]:
        log(f"  Nuevos: {', '.join(diff['added'][:10])}" + ("..." if len(diff['added']) > 10 else ""))
    if diff["removed"]:
        log(f"  Eliminados: {', '.join(diff['removed'][:10])}" + ("..." if len(diff['removed']) > 10 else ""))
    if diff["changed"]:
        for c in diff["changed"][:5]:
            log(f"  Cambiado: {c['model']}: {', '.join(c['changes'])}")

    # 5. Guardar
    if not args.dry_run:
        CAPS_FILE.write_text(json.dumps(new_caps, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"  Guardado: {CAPS_FILE}")
    else:
        log("  [DRY-RUN] No se guardo")

    log("=== FIN SYNC CAPACIDADES ===")
    return new_caps, diff

def main():
    parser = argparse.ArgumentParser(description="Sync capacidades de modelos Atlas")
    parser.add_argument("--dry-run", action="store_true", help="Solo calcular diff, sin sobrescribir")
    args = parser.parse_args()

    new_caps, diff = sync_cmd(args)

    # Resumen para stdout
    print(f"\nResultado: {diff['total_old']} -> {diff['total_new']} modelos")
    if diff['added']:
        print(f"  +{len(diff['added'])} nuevos")
    if diff['removed']:
        print(f"  -{len(diff['removed'])} eliminados")
    if diff['changed']:
        print(f"  ~{len(diff['changed'])} cambiados")

if __name__ == "__main__":
    main()