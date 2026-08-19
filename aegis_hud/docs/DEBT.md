# DEUDA TECNICA - AEGIS-JARVIS HUD

| DEBT-ID | ORIGEN | RIESGO | IMPACTO | MITIGACION | SOLUCION | RESPONSABLE | FECHA |
|---------|--------|--------|---------|------------|----------|-------------|-------|
| DEBT-001 | Captura pantalla mouse tiempo real | Rendimiento GPU vs log texto | MEDIO | Deshabilitado por defecto, solo bajo demanda | Implementar en V2 usando playwright-visual pw_screenshot | Dev | 2026-08-18 |
| DEBT-002 | Auto-deteccion puertos MCP | Configuracion hardcodeada en .env | BAJO | Documentado en .env.example | Health-scan puertos 20128-20140 al iniciar bridge | Dev | 2026-08-18 |
| DEBT-003 | Persistencia geometria ventana | Posicion/resize no guardada | BAJO | Ventana siempre en esquina sup. der. | Guardar/restaurar en QSettings en V2 | Dev | 2026-08-18 |
| DEBT-004 | Historial comandos (flecha arriba) | UX repetitiva | BAJO | Buffer en memoria actual | Anadir QCompleter en InputWidget V2 | Dev | 2026-08-18 |
| DEBT-005 | Notificaciones toast sistema | Alertas guardian/health no visibles | BAJO | Solo log en HUD | Integrar windows_toast o plyer V2 | Dev | 2026-08-18 |

**Formato segun GOVERNANCE.md Seccion 13**