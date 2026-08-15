# Baseline de Fricción — Atlas (P-5)

**Fecha:** 15/08/2026  
**Versión:** 1.0  
**Propósito:** Baseline medido ANTES de C3v2/C4. Meta: −50% tras C3v2+C4.

---

## Metodología

- **Período:** 7 días (08/08/2026 – 15/08/2026)
- **Fuente:** `state/friction_log.jsonl` + `/api/friction/weekly`
- **Eventos instrumentados:** 4 tipos (corrección, repetición, espera>10s, "no")

---

## Resultados Baseline (Semana 32, 2026)

| Semana | Eventos totales | Corrección | Repetición | Espera >10s | "No" |
|--------|-----------------|------------|------------|-------------|------|
| 2026-W32 | **5** | 2 | 1 | 1 | 1 |

**Total baseline: 5 eventos de fricción en 7 días**

---

## Detalle por tipo

| Tipo | Cuenta | % del total |
|------|--------|-------------|
| corrección | 2 | 40% |
| repetición | 1 | 20% |
| espera >10s | 1 | 20% |
| negativa ("no") | 1 | 20% |

---

## Objetivo C3v2+C4 (P-5)

> **Meta: −50% fricción tras C3v2+C4**
> - Baseline: 5 eventos/semana
> - Objetivo: ≤2.5 eventos/semana (redondeo: ≤2 eventos/semana)

---

## Verificación

```bash
# Ver baseline actual
curl http://127.0.0.1:4100/api/friction/weekly
# {"weeks":[{"week":"2026-W32","count":5}],"total":5}

# Ver eventos crudos
cat memory_data/state/friction_log.jsonl
```

---

## Próximos pasos

1. Implementar C3v2 (Auto-Modelo Vivo) → reducir "espera >10s" y "repetición"
2. Implementar C4 (Intención Profunda) → reducir "corrección" y "negativa"
3. Medir semanalmente vía `/api/friction/weekly` y panel dashboard
4. Comparar vs baseline al cierre de C3v2+C4

---

**Firmado:** Atlas Core  
**Fecha:** 15/08/2026  
**Commit:** `(pendiente)`