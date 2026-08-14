# ============================================================
# atlas_metrics.py — Métricas de uso/costo por modelo
# ------------------------------------------------------------
# Acumula registros de uso (modelo, tokens, costo estimado, latencia)
# y genera informes por día/semana/modelo.
#
# Los costos se estiman con la tabla PRICING por token (proveedor/modelo).
#
# Uso:
#   python atlas_metrics.py record --model omniroute/auto/best-coding \
#       --tokens-in 1200 --tokens-out 400 --latency-ms 3500
#   python atlas_metrics.py report --period week [--by-model]
#   python atlas_metrics.py report --period today
#   python atlas_metrics.py --stats          # resumen global
# ============================================================
import json
import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
MEMORY_ROOT = ROOT / "memory_data"
STATE_DIR = MEMORY_ROOT / "state"
USAGE_FILE = STATE_DIR / "usage_log.json"
ROUTING_FILE = STATE_DIR / "routing_log.json"

# Costos estimados por millón de tokens (USD) por proveedor base
PRICING = {
    # proveedor base -> (input_usd_M, output_usd_M)
    "omniroute": (0.15, 0.60),   # rango de modelos agrupados
    "9router":   (0.20, 0.80),
    "ollama":    (0.0, 0.0),     # local, sin costo
}

DEFAULT_CAP = 500  # entradas máximas en el log


def _load_usage():
    if USAGE_FILE.exists():
        try:
            return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"records": [], "total_cost_usd": 0.0}


def _save_usage(data):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"  Error guardando uso: {e}")


def _provider_of(model):
    """Proveedor base a partir de 'provider/modelo'"""
    if "/" in model:
        return model.split("/", 1)[0]
    return "unknown"


def estimate_cost(model, tokens_in, tokens_out):
    """Estima costo en USD de una llamada"""
    provider = _provider_of(model)
    price_in, price_out = PRICING.get(provider, (0.0, 0.0))
    cost = (tokens_in / 1_000_000) * price_in + (tokens_out / 1_000_000) * price_out
    return round(cost, 6)


def record(model, tokens_in, tokens_out, latency_ms=0, source="manual"):
    """Registra una llamada con uso/costo"""
    cost = estimate_cost(model, tokens_in, tokens_out)
    entry = {
        "ts": datetime.now().isoformat(),
        "model": model,
        "provider": _provider_of(model),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "cost_usd": cost,
        "source": source,
    }
    data = _load_usage()
    data["records"].append(entry)
    data["records"] = data["records"][-DEFAULT_CAP:]
    data["total_cost_usd"] = round(sum(r["cost_usd"] for r in data["records"]), 6)
    _save_usage(data)
    return entry


def _last_iso(period):
    """Devuelve el ISO cutoff del periodo"""
    now = datetime.now()
    if period == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    else:
        return None
    return cutoff.isoformat()


def report(period="week", by_model=False):
    """Genera informe de uso/costo"""
    data = _load_usage()
    records = data.get("records", [])

    if period == "today":
        cutoff = _last_iso("today")
    elif period == "week":
        cutoff = _last_iso("week")
    elif period == "month":
        cutoff = _last_iso("month")
    else:
        cutoff = None  # todo

    filtered = records if cutoff is None else [r for r in records if r["ts"] >= cutoff]

    if not filtered:
        print(f"No hay registros de uso para el periodo '{period}'")
        return {}

    total_in = sum(r["tokens_in"] for r in filtered)
    total_out = sum(r["tokens_out"] for r in filtered)
    total_cost = round(sum(r["cost_usd"] for r in filtered), 6)

    print(f"\n=== INFORME DE USO ({period}, {len(filtered)} llamadas) ===")
    print(f"Tokens in: {total_in:,}  |  Tokens out: {total_out:,}")
    print(f"Costo total estimado: ${total_cost:.4f}")

    if by_model:
        print(f"\nPor modelo:")
        print(f"  {'Modelo':<42} {'Llamadas':<9} {'Tok in':<10} {'Tok out':<10} {'Costo $'}")
        print("  " + "-" * 85)
        agg = defaultdict(lambda: {"calls": 0, "in": 0, "out": 0, "cost": 0.0})
        for r in filtered:
            a = agg[r["model"]]
            a["calls"] += 1
            a["in"] += r["tokens_in"]
            a["out"] += r["tokens_out"]
            a["cost"] += r["cost_usd"]
        for model, a in sorted(agg.items(), key=lambda x: -x[1]["cost"]):
            print(f"  {model:<42} {a['calls']:<9} {a['in']:<10,} {a['out']:<10,} ${a['cost']:.4f}")

    # Guardar snapshot en state para consulta rápida
    snapshot = {
        "updated": datetime.now().isoformat(),
        "period": period,
        "calls": len(filtered),
        "tokens_in": total_in,
        "tokens_out": total_out,
        "cost_usd": total_cost,
    }
    (STATE_DIR / "usage_snapshot.json").write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return snapshot


def ingest_from_routing():
    """Importa decisiones de routing_log como metricas de uso (estimacion)"""
    if not ROUTING_FILE.exists():
        print("  No hay routing_log.json para ingestar")
        return 0
    try:
        routing = json.loads(ROUTING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return 0

    ingested = 0
    for e in routing.get("entries", []):
        model = e.get("model_after") or e.get("model")
        decision = e.get("decision")
        if not model:
            continue
        if decision not in ("proceed", "switch", "keep"):
            continue
        # Estimacion: 800 tok in / 200 tok out como baseline por decision
        record(model=model, tokens_in=800, tokens_out=200,
               latency_ms=e.get("latency_ms", 0), source="routing_ingest")
        ingested += 1
    return ingested


def stats():
    """Resumen global"""
    data = _load_usage()
    records = data.get("records", [])
    total_cost = data.get("total_cost_usd", 0.0)
    total_tokens = sum(r["tokens_in"] + r["tokens_out"] for r in records)
    print(f"Registros: {len(records)}")
    print(f"Tokens totales: {total_tokens:,}")
    print(f"Costo total estimado: ${total_cost:.4f}")

    # Por provider
    print(f"\nPor provider:")
    print(f"  {'Provider':<12} {'Llamadas':<9} {'Costo $'}")
    agg = defaultdict(lambda: {"calls": 0, "cost": 0.0})
    for r in records:
        agg[r["provider"]]["calls"] += 1
        agg[r["provider"]]["cost"] += r["cost_usd"]
    for prov, a in sorted(agg.items(), key=lambda x: -x[1]["cost"]):
        print(f"  {prov:<12} {a['calls']:<9} ${a['cost']:.4f}")
    return {"records": len(records), "tokens": total_tokens, "cost_usd": total_cost}


def main():
    parser = argparse.ArgumentParser(description="Métricas de uso/costo de modelos")
    sub = parser.add_subparsers(dest="command")

    p_rec = sub.add_parser("record", help="Registrar una llamada")
    p_rec.add_argument("--model", required=True)
    p_rec.add_argument("--tokens-in", type=int, required=True)
    p_rec.add_argument("--tokens-out", type=int, required=True)
    p_rec.add_argument("--latency-ms", type=int, default=0)

    p_rep = sub.add_parser("report", help="Informe de uso")
    p_rep.add_argument("--period", choices=["today", "week", "month", "all"], default="week")
    p_rep.add_argument("--by-model", action="store_true")

    sub.add_parser("ingest", help="Ingestar routing_log como uso")
    sub.add_parser("stats", help="Resumen global")

    args = parser.parse_args()

    if args.command == "record":
        e = record(args.model, args.tokens_in, args.tokens_out, args.latency_ms)
        print(f"Registrado: {e['model']} | cost=${e['cost_usd']:.6f}")

    elif args.command == "report":
        report(args.period, args.by_model)

    elif args.command == "ingest":
        n = ingest_from_routing()
        print(f"Ingestados {n} registros desde routing_log")

    elif args.command == "stats":
        stats()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()