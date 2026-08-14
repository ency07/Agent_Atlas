# ============================================================
# tests/unit/test_search.py — Tests de búsqueda (FTS5 + web)
# ------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from atlas_search import web_search, web_research

def test_web_search_returns_results():
    results = web_search("python programming", max_results=3)
    assert isinstance(results, list)
    assert len(results) <= 3
    if len(results) > 0:
        assert "title" in results[0]
        assert "url" in results[0]
        assert "snippet" in results[0]

def test_web_research_returns_summary():
    result = web_research("test topic", depth=1)
    assert "summary" in result
    assert "note_path" in result
    assert "sources" in result

if __name__ == "__main__":
    test_web_search_returns_results()
    test_web_research_returns_summary()
    print("✅ tests/unit/test_search.py: OK")