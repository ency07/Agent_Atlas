---
id: 20260814-121159-20260814-tareas-alta-completadas-logrota
type: summary
project: agente_ia
tags: [roadmap,logrotate,bootcheck,backup,age,atlas]
created: 2026-08-14T17:11:59+00:00
source: opencode
status: active
links:
---

Se completaron las 3 tareas ALTA del roadmap tras F1/F3:

1. **Rotación de logs** (`atlas_logrotate.py`): rota logs 7 días, comprime .gz, limpia errors.jsonl (10000 líneas). Tarea `AtlasLogRotate` diaria 04:00.

2. **Boot check E2E** (`atlas_bootcheck.py`): verifica daemon memoria, dashboard web (:4100/api/health), proveedores IA (omniroute:20128, 9router:4000, ollama:11434), venv. Toast verde/rojo/amarillo. Tarea `AtlasBootCheck` en logon. Nota: requiere win10toast.

3. **Backup cifrado con age** (`atlas_backup_encrypted.py`): tarball gz + cifrado age via API directa (Encryptor/Decryptor de age.file). Comandos: backup/decrypt/list/generate. Claves en `.age_keys/` (gitignore'd). Tarea `AtlasEncryptedBackup` diaria 03:30.

Verificación: 40 unit tests PASS + 15 config tests PASS. Commits: f9356a7 (logrotate), 09319f7 (bootcheck), 277ec86 (backup cifrado).

Detalles técnicos aprendidos:
- age en Windows: la CLI (`python -m age.cli`) falla con encoding en recipients; usar API directa `from age.file import Encryptor, Decryptor` y `from age.keyloader import resolve_public_key, load_keys_txt`. La salida de `age generate` va a stderr.
- El dashboard web responde lento (~4s en /api/health), timeout de bootcheck debe ser >5s.
- Emojis (✅❌) fallan en consola Windows cp1252; usar [OK]/[FAIL].
