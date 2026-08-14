# Clonar Atlas en otra PC (100% funcional)

Guía paso a paso para llevar este repo a un PC nuevo y que Atlas quede corriendo completo, sin secretos comprometidos y con todos los servicios activos.

---

## 0. Qué lleva el repo y qué NO

### SÍ viaja en git
| Item | Dónde |
|---|---|
| Todo el código Python (core, chat, daemon, foco, salud, orquestador, search, guardian, metrics, backup, supervisor) | raíz `*.py` |
| Servers MCP de Windows/Corel/Playwright | `mcp_windows/` |
| Plantillas de config | `templates/` |
| La bóveda de memoria (notas Obsidian) | `memory_data/vault/` |
| Git hook post-commit | `hooks/` |
| Scripts `.vbs` (autostart de todo) | raíz `*.vbs` |
| Bootstrap y diagnóstico | `setup.ps1`, `check.ps1` |
| Tests (unit + config) | `tests/` |
| Roadmap y SPEC de C1 | `Roadmap v1.4.html`, `SPEC_C1.html` |

### NO viaja (se regenera o se configura en la PC nueva)
| Item | Por qué | Cómo en la PC nueva |
|---|---|---|
| `.venv/` | dependencias Python | `setup.ps1` lo crea |
| `memory_data/state/` | SQLite + flags del sistema | se genera al primer uso |
| `memory_data/backup/` | backups locales | primero `git clone` → después `setup.ps1` |
| `.env` | secretos | **lo crea el usuario** (nunca se commitea) |
| `.age_keys/` | claves cifrado backup | `python atlas_backup_encrypted.py generate` |
| `node_modules/`, `.pytest_cache/`, `logs/`, `tmp/` | salidas | se generan solas |

---

## 1. Requisitos previos del PC nuevo

| Requisito | Versión | Link |
|---|---|---|
| Windows 10/11 | — | — |
| Node.js | **>= 20** | https://nodejs.org/en/download |
| Python | **>= 3.11** (para mcp<2 no usar 3.13 con wheels faltantes) | https://www.python.org/downloads/ |

> Marca "Add to PATH" en el instalador de Python. En Node es automático.

**Verificar en PowerShell:**
```powershell
node -v      # debe decir v20.x o superior
python --version   # 3.11.x
```

---

## 2. Clonar el repo

```powershell
git clone https://github.com/ency07/Agent_Atlas
cd Agent_Atlas
```

---

## 3. Instalar los PROVIDERS de modelos

Atlas necesita al menos un proveedor de modelos. Hay 3 opciones (puedes tener todas):

### Opción A — OmniRoute (recomendada, 260+ modelos auto/*)
```powershell
npm install -g omniroute
```
Docs oficiales: https://github.com/ency07/omniroute   *(link de referencia)*

### Opción B — 9Router (679 modelos: Groq, Gemini, OpenRouter, etc.)
```powershell
npm install -g 9router
```
Docs oficiales: https://github.com/9router/9router   *(link de referencia)*

### Opción C — Ollama (fallback local, sin costo, modelos 1–8B)
```powershell
winget install Ollama.Ollama
# o manual:  https://ollama.ai/download
ollama pull qwen2.5:1.5b   # modelo mínimo
ollama pull phi4-mini
```

> **Nota sobre API keys:** OmniRoute y 9Router corren en localhost (`:20128` y `:4000`).
> No necesitan key externa para funcionar como proxy local de tus modelos.
> Si quieres acceder a LLMs remotos a través de ellos, configura sus propias
> credenciales según su documentación, **siempre en archivos `.env` fuera del repo**.

---

## 4. Ejecutar el bootstrap

```powershell
powershell -ExecutionPolicy Bypass -File setup.ps1
```

Esto hace, automáticamente:
1. Verifica Node y Python
2. Instala `opencode-ai` global (si falta): `npm install -g opencode-ai`
3. Crea `.venv` e instala `requirements.txt` (pip: mcp, mcp-server-git, pywebview, playwright, psutil, ddgs, age, ...)
4. Genera `%USERPROFILE%\.config\opencode\opencode.jsonc` desde la plantilla
   (incluye solo los providers que DETECTA activos)
5. Instala los skills: `memory` y `atlas_orchestrator`
6. Copia `model_capabilities.json`, `guardian.json`, `search.json`, `foco_rules.json`
7. Configura el git hook `hooks/post-commit`
8. Registra TODAS las tareas de Windows (Task Scheduler):

| Tarea | Trigger | Qué hace |
|---|---|---|
| `AtlasBackup` | diario 03:00 | backup zip |
| `AtlasEncryptedBackup` | diario 03:30 | backup cifrado age |
| `AtlasLogRotate` | diario 04:00 | rotación de logs (7 días) |
| `AtlasActivity` | ONLOGON | daemon de actividad + bandeja |
| `AtlasChat` | ONLOGON | chat flotante |
| `AtlasOmniRoute` | ONLOGON | proxy omniroute |
| `Atlas9Router` | ONLOGON | proxy 9router |
| `AtlasWeb` | ONLOGON | dashboard :4100 |
| `AtlasSupervisor` | ONLOGON | auto-reparación |
| `AtlasBootCheck` | ONLOGON | check + toast |
| `AtlasSecretReminder` | dom 09:00 | recordatorio rotación secretos |
| `AtlasSyncCapabilities` | lun 03:15 | refresh model_capabilities.json |
| `AtlasBenchmark` | lun 03:20 | latencia/éxito por provider |
| `AtlasMetrics` | lun 03:25 | uso/costo por modelo |

9. Ejecuta `check.ps1` (diagnóstico final)

---

## 5. Secretos (CRÍTICO — nunca se versionan)

| Secreto | Dónde crearlo | Formato |
|---|---|---|
| `OMNIROUTE_API_KEY` | variable de usuario Windows | `[Environment]::SetEnvironmentVariable("OMNIROUTE_API_KEY","sk-...","User")` |
| `NINEROUTER_API_KEY` | variable de usuario Windows | igual que arriba |
| Claves age | `.age_keys/` en el repo | `python atlas_backup_encrypted.py generate` |

El `.env.example` del repo es la plantilla; cópialo como `.env` local si necesitas sobrescribir valores, **nunca lo commitees** (`.gitignore` lo bloquea).

---

## 6. Generar claves age del backup cifrado

```powershell
python atlas_backup_encrypted.py generate
```
Guarda la **clave privada** en un lugar seguro (NO en el repo). Para probar:
```powershell
python atlas_backup_encrypted.py backup
python atlas_backup_encrypted.py list
```

---

## 7. Verificación final (todo checklist)

```powershell
powershell -ExecutionPolicy Bypass -File check.ps1
```

Debe salir todo en verde: daemon, proveedores (`omniroute:20128`, `9router:4000`, `ollama:11434`), venv, config, bóveda.

Además, manual:
```powershell
python mcp_memory_server.py --cli health      # memoria + DB
opencode run "dime donde quedamos"            # memoria carga en opencode
open http://127.0.0.1:4100/api/health         # dashboard
```

---

## 8. Si algo falla por provider no detectado

1. Instala el provider (sección 3).
2. Reinicia la terminal (para refrescar PATH de npm global).
3. Vuelve a ejecutar `setup.ps1`.
4. Si ya configuraste y quieres regenerar solo el jsonc:
   ```powershell
   powershell -ExecutionPolicy Bypass -File setup.ps1
   ```

---

## 9. Rollback rápido

```powershell
# volver al último punto estable
git log --oneline -5
git checkout <sha_estable>
# restaurar memoria si hace falta
python mcp_memory_server.py --cli restore --backup-file memory_data\backup\atlas_*.zip
```

---

## Ruta de troubleshooting

- [`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — fallos comunes
- [`docs/PUESTA_EN_MARCHA.md`](PUESTA_EN_MARCHA.md) — puesta en marcha detallada
- [`docs/CONFIG_OPCODE.md`](CONFIG_OPCODE.md) — config de opencode
- [`docs/QUE_NO_HACER.md`](QUE_NO_HACER.md) — errores prohibidos

---

Atlas · `docs/CLONAR_EN_OTRA_PC.md` · E:\Agente_IA