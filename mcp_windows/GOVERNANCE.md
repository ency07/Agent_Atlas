# 📋 Marco de Trabajo: Gobernanza de Desarrollo (Protocolo de IA)

Este documento define las reglas de compromiso y el marco de trabajo obligatorio para cualquier interacción con el código base. **Toda intervención debe seguir estrictamente este flujo de estados.**

## 1. Reglas de Compromiso (Constitution)
- **Principio de Integridad:** Nunca asumas librerías o funcionalidades. Si no está en el `package.json` o archivos de configuración, verifica primero.
- **Trazabilidad:** Toda decisión técnica debe estar vinculada a un ADR (Architectural Decision Record).
- **Calidad:** Ningún código se considera "completado" sin su correspondiente test (Vitest/Playwright).
- **Estándar:** Se prioriza el rendimiento (SvelteKit + PWA) y la seguridad (RLS + Cifrado en reposo).

## 2. Flujo de Trabajo (Protocolo de Estados)
Cualquier solicitud de desarrollo debe procesarse en este orden exacto:

1.  **`/constitution`**: Definición de reglas y estándares base.
2.  **`/specify`**: ¿Qué vamos a construir y por qué? (Propósito de negocio).
3.  **`/clarify`**: Identificación de huecos, ambigüedades y dudas técnicas. *La IA debe detenerse y preguntar.*
4.  **`/plan`**: Definición del stack, arquitectura, ADRs aplicables y estrategia de datos.
5.  **`/tasks`**: Desglose granular en tareas pequeñas, accionables y verificables.
6.  **`/analyze`**: Revisión de consistencia: ¿Las tareas cubren la especificación? ¿Es coherente con el stack?
7.  **`/implement`**: Ejecución técnica. Cada implementación debe incluir un **checkpoint de validación** antes de pasar a la siguiente tarea.

## 3. Principios de Implementación
- **Micro-commits:** Cada tarea debe resultar en un estado funcional (aunque sea parcial).
- **Verificación:** Si el framework de pruebas existente no cubre la nueva funcionalidad, la primera tarea de `/implement` es añadir dicho test.
- **Comunicación:** La IA no debe añadir comentarios descriptivos en el código ("he cambiado esto porque..."). La traza de cambios debe estar en el historial del repositorio y en los archivos de tareas.

## 4. Gestión de Deuda Técnica
- Toda decisión técnica que se aleje de los estándares definidos debe documentarse como una **"Deuda Operativa"** en `README.md` bajo la sección correspondiente.
