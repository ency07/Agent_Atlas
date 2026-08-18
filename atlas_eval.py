#!/usr/bin/env python3
"""atlas_eval.py — Evaluacion mensual de capacidades de Atlas (REQ-C15).

Ejecuta un conjunto fijo de casos con rubrica, guarda resultados en
state/evals/YYYY-MM.json y los expone en el dashboard via /api/evals.

Uso:
    python atlas_eval.py run          # ejecuta la bateria mensual
    python atlas_eval.py report       # ultimo resultado
    python atlas_eval.py schedule     # crea la tarea programada (lunes 03:30)

Bateria (5 casos):
    E1 memoria-inicial  -> memory_summary responde con identidad
    E2 memoria-guardar  -> note_save + note_search roundtrip
    E3 informe-entrega  -> publish_report genera html en outputs/
    E4 checkpoint       -> checkpoint save/resume roundtrip
    E5 redaccion        -> redact() oculta token sembrado
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
STATE = ROOT / "memory_data" / "state"
EVAL_DIR = STATE / "evals"
EVAL_DIR.mkdir(parents=True, exist_ok=True)

# Escala: 0 = fallo, 1 = parcial, 2 = completo
RUBRICA = {
    "E1": {"name": "memoria-inicial", "target": "memory_summary devuelve identidad y estado", "max": 2},
    "E2": {"name": "memoria-guardar", "target": "note_save + note_search roundtrip sin perdida", "max": 2},
    "E3": {"name": "informe-entrega", "target": "publish_report publica html en outputs/", "max": 2},
    "E4": {"name": "checkpoint", "target": "checkpoint save/resume conserva contexto", "max": 2},
    "E5": {"name": "redaccion", "target": "redact() oculta token sembrado en entrega", "max": 2},
    "E6": {"name": "dashboard-live", "target": "/api/live responde con health_status y tasks", "max": 2},
    "E7": {"name": "orden-l0", "target": "POST /api/orden L0/L1 ejecuta fast-path sin contrato", "max": 2},
    "E8": {"name": "overlay-activo", "target": "atlas_overlay.py proceso vivo (proceso o tarea ONLOGON)", "max": 2},
}


def run_case_e1():
    sys.path.insert(0, str(ROOT))
    import mcp_memory_server as mem
    try:
        r = json.loads(mem.tool_summary(project="agente_ia", budget=800))
        ctx = str(r.get("context", "")) if isinstance(r, dict) else str(r)
        if r and ("identidad" in ctx.lower() or "objetivo" in ctx.lower() or "estado" in ctx.lower()):
            return 2, ""
        return 1, f"summary sin identidad/estado: {ctx[:120]}"
    except Exception as e:
        return 0, str(e)


def run_case_e2():
    import mcp_memory_server as mem
    try:
        import re
        token = "eval" + re.sub(r"\D", "", datetime.now().strftime("%H%M%S"))
        save = json.loads(mem.tool_note_save(f"Eval roundtrip {token}", "contenido de prueba", "fact", project="test", tags="eval"))
        if not save.get("success"):
            return 0, f"save fallo: {save}"
        found = mem.tool_note_search(token, project="test", limit=5)
        try:
            found = json.loads(found) if isinstance(found, str) else found
        except Exception:
            pass
        count = found.get("count", 0) if isinstance(found, dict) else 0
        if count >= 1:
            return 2, ""
        return 1, f"search no encontro el token: {found}"
    except Exception as e:
        return 0, str(e)


def run_case_e3():
    import mcp_memory_server as mem
    try:
        tmp = ROOT / "tmp"
        tmp.mkdir(exist_ok=True)
        html = tmp / "eval_informe.html"
        html.write_text("<html><body><h1>Eval C1</h1></body></html>", encoding="utf-8")
        r = json.loads(mem.tool_publish_report(str(html), title=f"Eval C1 {datetime.now().strftime('%H%M%S')}", level="L2"))
        if r.get("success"):
            return 2, ""
        return 1, f"publish sin success: {r}"
    except Exception as e:
        return 0, str(e)


def run_case_e4():
    import atlas_checkpoints as cp
    try:
        task = "eval-cp-" + datetime.now().strftime("%H%M%S")
        cp.save(task, steps=["a", "b", "c"], current_step=1, context={"x": 1})
        r = cp.resume(task)
        ok = r and r["current_step"] == 1 and r["context"].get("x") == 1
        cp.clear(task)
        return (2, "") if ok else (1, f"checkpoint corrupto: {r}")
    except Exception as e:
        return 0, str(e)


def run_case_e5():
    import mcp_memory_server as mem
    try:
        seeded = "entregable con token sk-eval1234567890abcdef secreto"
        out = mem.redact(seeded)
        if "REDACTED" in out and "sk-eval" not in out:
            return 2, ""
        return 1, f"redact no oculto token: {out}"
    except Exception as e:
        return 0, str(e)


def run_case_e6():
    """GET /api/live → 200 con health_status + tasks."""
    import urllib.request
    try:
        r = urllib.request.urlopen("http://127.0.0.1:4100/api/live", timeout=8)
        data = json.loads(r.read())
        if data.get("health_status") and "tasks" in data:
            return 2, ""
        return 1, f"live incompleto: {list(data.keys())}"
    except Exception as e:
        return 0, str(e)


def run_case_e7():
    """POST /api/orden L0/L1 → ok + requires_confirmation=false."""
    import urllib.request
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:4100/api/orden",
            data=json.dumps({"texto": "abre el navegador"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        r = urllib.request.urlopen(req, timeout=15)
        data = json.loads(r.read())
        if data.get("ok") and data.get("requires_confirmation") is False:
            return 2, ""
        return 1, f"orden no fast-path: {data}"
    except Exception as e:
        return 0, str(e)


def run_case_e8():
    """atlas_overlay.py vivo (proceso corriendo o tarea ONLOGON registrada)."""
    import subprocess
    try:
        for p in subprocess.Popen(
            ["wmic", "process", "where", "name like '%python%'", "get", "commandline"],
            stdout=subprocess.PIPE, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout:
            if "atlas_overlay.py" in p:
                return 2, ""
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["schtasks", "/Query", "/TN", "AtlasOverlay"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and "AtlasOverlay" in out.stdout:
            return 2, "tarea ONLOGON registrada (proceso no corriendo)"
    except Exception:
        pass
    return 1, "overlay no encontrado como proceso ni tarea"


CASES = {
    "E1": run_case_e1,
    "E2": run_case_e2,
    "E3": run_case_e3,
    "E4": run_case_e4,
    "E5": run_case_e5,
    "E6": run_case_e6,
    "E7": run_case_e7,
    "E8": run_case_e8,
}


def run_battery() -> dict:
    results = []
    total = 0
    for case_id, fn in sorted(CASES.items()):
        score, detail = fn()
        total += score
        results.append({
            "case": case_id,
            "name": RUBRICA[case_id]["name"],
            "target": RUBRICA[case_id]["target"],
            "score": score,
            "max": RUBRICA[case_id]["max"],
            "detail": detail,
        })
    month = datetime.now().strftime("%Y-%m")
    report = {
        "month": month,
        "run_at": datetime.now().isoformat(),
        "total": total,
        "max": sum(r["max"] for r in results),
        "pass_rate": round(total / sum(r["max"] for r in results) * 100, 1),
        "cases": results,
    }
    (EVAL_DIR / f"{month}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def report_last() -> dict:
    files = sorted(EVAL_DIR.glob("*.json"))
    if not files:
        return {"error": "sin evals todavia"}
    return json.loads(files[-1].read_text(encoding="utf-8"))


def schedule():
    """Crea la tarea programada AtlasEval (lunes 03:30)."""
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if not venv.exists():
        venv = Path(sys.executable)
    script = ROOT / "atlas_eval.py"
    action = f'"{venv}" "{script}" run'
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Atlas C1: evaluacion mensual de capacidades (REQ-C15)</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{datetime.now().strftime('%Y-%m-%d')}T03:30:00</StartBoundary>
      <ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><Monday/></DaysOfWeek></ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries></Settings>
  <Actions Context="Author"><Exec><Command>{action}</Command></Exec></Actions>
</Task>"""
    tmp = ROOT / "tmp" / "atlas_eval_task.xml"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(xml, encoding="utf-16")
    try:
        subprocess.run(["schtasks", "/Create", "/TN", "AtlasEval", "/XML", str(tmp), "/F"],
                       check=True, capture_output=True)
        return {"created": True, "task": "AtlasEval", "schedule": "Lunes 03:30"}
    except Exception as e:
        return {"created": False, "error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "report", "schedule"])
    args = ap.parse_args()
    if args.cmd == "run":
        print(json.dumps(run_battery(), ensure_ascii=False, indent=2))
    elif args.cmd == "report":
        print(json.dumps(report_last(), ensure_ascii=False, indent=2))
    elif args.cmd == "schedule":
        print(json.dumps(schedule(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
