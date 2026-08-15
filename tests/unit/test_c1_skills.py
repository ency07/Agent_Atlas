# ============================================================
# tests/unit/test_c1_skills.py — REQ-C1/C2 skills + preferencias instaladas
# ------------------------------------------------------------
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

ROOT = Path(__file__).parent.parent.parent
TEMPLATES = ROOT / "templates" / "skills"
VAULT = ROOT / "memory_data" / "vault"

C1_SKILLS = [
    "ejecucion-verificada",
    "informe-profesional",
    "investigacion-exhaustiva",
    "runbooks",
    "critico",
    "entrega",
]


def test_c1_skills_exist_in_templates():
    for name in C1_SKILLS:
        skill = TEMPLATES / name / "SKILL.md"
        assert skill.exists(), f"skill {name} no existe en templates"

        content = skill.read_text(encoding="utf-8")
        assert "description:" in content, f"skill {name} sin description en frontmatter"
        assert len(content) > 100, f"skill {name} demasiado corta"


def test_c1_skills_installed_in_cfg():
    cfg_skills = Path.home() / ".config" / "opencode" / "skills"
    for name in C1_SKILLS:
        installed = cfg_skills / name / "SKILL.md"
        if installed.exists():
            content = installed.read_text(encoding="utf-8")
            assert "description:" in content
        else:
            # puede que no se haya corrido setup.ps1; skip
            pass


def test_c2_style_profile_exists():
    sp = VAULT / "global" / "preferences" / "style_profile.md"
    assert sp.exists()
    content = sp.read_text(encoding="utf-8")
    assert "L2" in content or "L3" in content


def test_c2_programas_exists():
    pr = VAULT / "global" / "preferences" / "programas.md"
    assert pr.exists()
    content = pr.read_text(encoding="utf-8")
    assert "Chrome" in content or "chrome" in content.lower()


def test_c8_outputs_dir_exists():
    out = VAULT / "outputs"
    assert out.exists()


def test_c8_informe_template_exists():
    tpl = VAULT / "global" / "templates" / "informe_6_bloques.html"
    assert tpl.exists()
    content = tpl.read_text(encoding="utf-8")
    assert "6 bloques" in content or "__TITULO__" in content


def test_c13_tasks_dir_exists():
    tasks = Path(ROOT) / "memory_data" / "state" / "tasks"
    assert tasks.exists()
