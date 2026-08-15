# ============================================================
# tests/unit/test_c1_academic.py — REQ-C9 web_research_academic
# ------------------------------------------------------------
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from atlas_search import web_research_academic


def test_academic_returns_structure(monkeypatch):
    # mock de requests para no depender de la red en CI
    class FakeResp:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data

    class FakeCrossrefResp(FakeResp):
        text = ""
        def __init__(self):
            super().__init__({"message": {"items": [
                {"title": ["Paper de prueba"], "DOI": "10.1000/xyz",
                 "URL": "https://doi.org/10.1000/xyz",
                 "author": [{"given": "Ana", "family": "Garcia"}],
                 "published-print": {"date-parts": [[2024]]}}
            ]}})

    class FakeArxivResp(FakeResp):
        def __init__(self):
            self.text = """<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>Arxiv Paper Test</title>
                <id>http://arxiv.org/abs/2401.00001</id>
                <published>2024-01-01T00:00:00Z</published>
                <author><name>Juan Perez</name></author>
                <summary>Un resumen del paper de prueba para el test.</summary>
              </entry>
            </feed>"""
            self._data = None
        def json(self):
            return {}
        def raise_for_status(self):
            pass

    import requests
    monkeypatch.setattr(requests, "get", lambda url, **kw: (
        FakeArxivResp() if "arxiv" in url else FakeCrossrefResp()))

    r = web_research_academic("prueba", max_results=3)
    assert "results" in r
    assert len(r["results"]) >= 2  # crossref + arxiv

    # ambos sources presentes
    sources = {res["source"] for res in r["results"]}
    assert "crossref" in sources
    assert "arxiv" in sources

    # estructura de cada resultado
    for res in r["results"]:
        assert "title" in res
        assert "authors" in res
        assert "url" in res
        assert "source" in res


def test_academic_no_network_fallback(monkeypatch):
    def boom(url, **kw):
        raise Exception("sin red")
    import requests
    monkeypatch.setattr(requests, "get", boom)
    r = web_research_academic("algo", max_results=3)
    assert "results" in r
    assert len(r["results"]) == 0 or "note" in r
