---
id: 20260814-142802-20260814-push-github-completado-docs-clo
type: session
project: agente_ia
tags: [github, push,roadmap,f2.5,c1,docs]
created: 2026-08-14T19:28:02+00:00
source: opencode
status: active
links:
---

Push a GitHub completado: https://github.com/ency07/Agent_Atlas

Trabajo realizado en esta sesión (completo desde F2.5 ALTA hasta la publicación):

**F2.5 ALTA (commit 6db3e2d):**
1. Fix de chat: atlas_chat.py usaba `import datetime` + `datetime.now()` = NameError silencioso en logon. Fix con `from datetime import datetime`.
2. AtlasOmniRoute ONLOGON: creado start_omniroute.vbs + tarea Task Scheduler.
3. Orquestador default: vision_supported API fix (siempre presente en todas las ramas).

**MEDIA completadas (commits 0adb530, 6153fe1, 04b12e4, 5690da8):**
1. Auto-sync capacidades (atlas_sync_capabilities.py)
2. Benchmark real (atlas_benchmark.py)
3. Auto-cambio modelo runtime (atlas_model_switch.py)
4. Metricas uso/costo (atlas_metrics.py)

**Documentación (commit e9f3aa1):**
- docs/CLONAR_EN_OTRA_PC.md: guía paso a paso para clonar en otra PC
  (providers con links, setup, secretos, age, checklist, troubleshooting)
- setup.ps1 simplificado (sin wizard, apunta a la doc)
- HANDOFF.md actualizado

**Repo publicado:** https://github.com/ency07/Agent_Atlas
Verificación: 78/78 unit tests PASS, 15/15 config tests PASS, sin secretos comprometidos.

**Roadmap siguiente:** C1 Ejecución Profesional (6 skills, windows MCP, /api/informes, estándar 6 bloques, SPEC_C1.html)
