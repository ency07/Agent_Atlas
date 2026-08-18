# ADR 005 — Aceptación de warnings de thread‑leak en test harness

**Fecha:** 15/08/2026  
**Estado:** Aceptado (no bloqueante)  

## Contexto
Al ejecutar la suite completa de tests (`pytest tests/`) aparecen 2 warnings:

```
pytest.PytestUnhandledThreadExceptionWarning: Thread leak in test harness (SystemExit from argparse)
```

Se originan en los tests que arrancan `atlas_web_server.py` en un hilo daemon (`test_p_friction.py`, `test_p_streaming.py`). El servidor usa `argparse` y termina con `SystemExit(2)` cuando se le pasa argumentos inválidos desde el hilo de test, lo que genera un thread que no se limpia antes de que pytest finalice.

## Decisión
**Aceptar** los warnings como **no bloqueantes** porque:

1. No afectan la funcionalidad productiva (el servidor en producción no se ejecuta bajo pytest).
2. No causan fugas de recursos en entorno real (el proceso principal termina limpiamente).
3. Corregir requeriría refactor del harness de test (usar `ThreadPoolExecutor` + proper shutdown) — esfuerzo mayor al riesgo actual.

## Alternativas consideradas
| Opción | Pros | Contras |
|--------|------|----------|
| Ignorar (actual) | Cero esfuerzo, sin impacto prod | Warnings visibles en CI |
| Refactor test harness (fixture `session` + graceful shutdown) | Limpia warnings | Tiempo de desarrollo, riesgo de regresión en tests |
| Suprimir warning con `filterwarnings` | Limpia salida | Oculta posible problema real |

Se elige **Ignorar** y registrar en ADR.

## Mitigación futura
- Al migrar a `pytest-asyncio` o `anyio` para servidores asíncronos, reemplazar hilos daemon por tareas cancelables.
- Añadir fixture `session` que haga `server.shutdown()` y `thread.join(timeout=2)`.

## Consecuencias
- No se considera deuda técnica (no se registra en DEBT.md).
- Documentado para auditoría y futuros revisores.

---  
*ADR generado conforme a plantilla de decisiones de arquitectura.*