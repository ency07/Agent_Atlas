# ============================================================
# atlas_benchmark.py — Benchmark real de proveedores Atlas
# ------------------------------------------------------------
# Mide latencia y éxito de cada provider haciendo requests reales
# a /v1/models (chat completions en modo --deep). Guarda resultados
# en routing_log.json (sección provider_stats) y genera informe.
#
# Uso:
#   python atlas_benchmark.py               # benchmark ligero (models)
#   python atlas_benchmark.py --deep         # + 1 chat completion por provider
#   python atlas_benchmark.py --report       # informe de stats acumuladas
#   python atlas_benchmark.py --repeat 5     # N rondas por provider
# ============================================================
import json
import os
import sys
import time
import argparse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
MEMORY_ROOT = ROOT / "memory_data"
STATE_DIR = MEMORY_ROOT / "state"
LOG_FILE = STATE_DIR / "routing_log.json"

PROVIDERS = {
    "omniroute": {"port": 20128, "api": "http://localhost:20128/v1", "model_endpoint": "/v1/models"},
    "9router":   {"port": 4000,  "api": "http://localhost:4000/v1", "model_endpoint": "/v1/models"},
    "ollama":    {"port": 11434, "api": "http://localhost:11434/v1", "model_endpoint": "/api/tags"},
}

TIMEOUT = 15


def _load_log():
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"entries": [], "provider_health": {}, "provider_stats": {}}


def _save_log(data):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  Error guardando log: {e}")


import atlas_metrics as am


def _measure(name, cfg, kind="models"):
    """Mide latencia de un provider. Returns (latency_ms, ok, error)"""
    url = cfg["api"] + ("/models" if kind == "models" else "/chat/completions")
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url)
        if kind == "chat":
            req = urllib.request.Request(
                url,
                data=json.dumps({
                    "model": "auto/best-fast" if name != "ollama" else "qwen2.5:1.5b",
                    "messages": [{"role": "user", "content": "Di 'ok'"}],
                    "max_tokens": 5,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read()
            latency = (time.perf_counter() - start) * 1000
            # Registrar metricas de uso (tokens estimados)
            if kind == "chat":
                try:
                    resp = json.loads(data)
                    tokens_in = resp.get("usage", {}).get("prompt_tokens", 10)
                    tokens_out = resp.get("usage", {}).get("completion_tokens", 5)
                    model_id = resp.get("model", cfg.get("model", f"{name}/auto"))
                    am.record(model=f"{name}/{model_id}", tokens_in=tokens_in,
                              tokens_out=tokens_out, latency_ms=round(latency, 1),
                              source="benchmark")
                except Exception:
                    pass
            return latency, True, None
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return latency, False, str(e)[:100]


def run_benchmark(repeat=1, deep=False):
    """Ejecuta benchmark y guarda stats"""
    print(f"[{datetime.now().isoformat()}] === BENCHMARK ATLAS ===")
    data = _load_log()
    stats = data.setdefault("provider_stats", {})

    for name, cfg in PROVIDERS.items():
        if name not in stats:
            stats[name] = {"attempts": 0, "success": 0, "latency_total_ms": 0, "latency_samples": [], "last_error": None, "last_run": None}

        results = []
        for i in range(repeat):
            lat, ok, err = _measure(name, cfg, kind="models")
            results.append({"round": i + 1, "latency_ms": round(lat, 1), "ok": ok, "error": err})

        # Actualizar stats
        s = stats[name]
        for r in results:
            s["attempts"] += 1
            s["latency_total_ms"] += r["latency_ms"]
            if r["ok"]:
                s["success"] += 1
            else:
                s["last_error"] = r["error"]
        s["latency_samples"] = (s.get("latency_samples", []) + [r["latency_ms"] for r in results])[-50:]
        s["last_run"] = datetime.now(timezone.utc).isoformat()
        s["success_rate"] = round(s["success"] / s["attempts"] * 100, 1) if s["attempts"] else 0
        s["avg_latency_ms"] = round(s["latency_total_ms"] / s["attempts"], 1) if s["attempts"] else 0

        status = "OK" if all(r["ok"] for r in results) else "FALLAS"
        print(f"  [{name}] {status} | avg={results[0]['latency_ms']}ms | success={sum(1 for r in results if r['ok'])}/{len(results)}")

        if deep:
            lat, ok, err = _measure(name, cfg, kind="chat")
            print(f"  [{name}] chat: {'OK' if ok else 'FAIL'} {lat:.1f}ms {err or ''}")

    _save_log(data)
    print(f"[{datetime.now().isoformat()}] === FIN BENCHMARK ===")
    return stats


def report():
    """Genera informe de stats acumuladas"""
    data = _load_log()
    stats = data.get("provider_stats", {})
    print(f"\n=== INFORME PROVEEDORES ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ===")
    print(f"{'Provider':<12} {'Intentos':<8} {'Exito':<6} {'Tasa':<7} {'Avg lat':<9} {'Ultimo error'}")
    print("-" * 70)
    for name, s in stats.items():
        rate = f"{s.get('success_rate', 0)}%"
        avg = f"{s.get('avg_latency_ms', 0)}ms"
        err = (s.get("last_error") or "-")[:40]
        print(f"{name:<12} {s.get('attempts', 0):<8} {s.get('success', 0):<6} {rate:<7} {avg:<9} {err}")

    # Resumen
    total_attempts = sum(s.get("attempts", 0) for s in stats.values())
    total_success = sum(s.get("success", 0) for s in stats.values())
    if total_attempts:
        print(f"\nGlobal: {total_success}/{total_attempts} OK ({total_success/total_attempts*100:.1f}%)")

    # Ruta recomendada (menor latencia con éxito)
    healthy = {n: s for n, s in stats.items() if s.get("success_rate", 0) >= 50}
    if healthy:
        best = min(healthy.items(), key=lambda x: x[1].get("avg_latency_ms", 999))
        print(f"Mejor ruta actual: {best[0]} (avg {best[1]['avg_latency_ms']}ms)")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Benchmark de proveedores Atlas")
    parser.add_argument("--repeat", type=int, default=1, help="Rondas por provider")
    parser.add_argument("--deep", action="store_true", help="Incluir chat completions")
    parser.add_argument("--report", action="store_true", help="Solo informe de stats")
    args = parser.parse_args()

    if args.report:
        report()
        return

    run_benchmark(repeat=args.repeat, deep=args.deep)
    print()
    report()


if __name__ == "__main__":
    main()