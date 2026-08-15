# ============================================================
# tests/unit/test_c1_publish_report.py — REQ-C8 publicacion de entregables
# ------------------------------------------------------------
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import mcp_memory_server as mcp_mem

def parse_result(result):
    if isinstance(result, str):
        return json.loads(result)
    return result


def test_publish_report_creates_output_and_index(tmp_path):
    html = tmp_path / "demo.html"
    html.write_text("<html><body><h1>Demo C1</h1></body></html>", encoding="utf-8")

    r = parse_result(mcp_mem.tool_publish_report(
        str(html), title="Demo C1", level="L2", note_body="informe de prueba"))

    assert r.get("success") is True
    assert "path" in r
    assert "id" in r
    assert r["url"].startswith("/informe/")

    out = Path(r["path"])
    assert out.exists()
    assert "outputs" in str(out)

    # index registrado
    idx = Path(mcp_mem.STATE_DIR) / "reports_index.json"
    assert idx.exists()
    data = json.loads(idx.read_text(encoding="utf-8"))
    assert any(e["id"] == r["id"] for e in data)

    # nota MD de respaldo creada
    note = Path(mcp_mem.VAULT_ROOT) / "global" / "notes" / (r["id"].replace("_", "-") + ".md")
    # el id es YYYYMMDD_HHMMSS-<titulo>; la nota se nombra con guiones
    candidates = list((Path(mcp_mem.VAULT_ROOT) / "global" / "notes").glob(f"*-{r['id'].split('-')[-1]}.md"))
    assert len(candidates) >= 1


def test_publish_report_missing_file():
    r = parse_result(mcp_mem.tool_publish_report("no_existe.html", title="x"))
    assert "error" in r


def test_publish_report_versioning(tmp_path):
    html = tmp_path / "v.html"
    html.write_text("<html></html>", encoding="utf-8")
    import time
    title = f"Version Test {int(time.time()*1000)}"
    r1 = parse_result(mcp_mem.tool_publish_report(str(html), title=title))
    r2 = parse_result(mcp_mem.tool_publish_report(str(html), title=title))
    assert r1["path"] != r2["path"]
    assert r1["path"].endswith("-v1.html")
    assert r2["path"].endswith("-v2.html")
