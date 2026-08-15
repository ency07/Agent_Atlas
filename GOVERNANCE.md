# 📋 Marco de Trabajo: Gobernanza de Desarrollo (Protocolo de IA)

Este documento define las reglas de compromiso y el marco de trabajo obligatorio para cualquier interacción con cualquier base de código, **independientemente del lenguaje, framework o stack tecnológico utilizado**. **Toda intervención debe seguir estrictamente este flujo de estados.**

## 1. Reglas de Compromiso (Constitution)
- **Principio de Integridad:** Nunca asumas librerías, dependencias o funcionalidades. Si no está declarado en el manifiesto de dependencias del proyecto (`package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `*.csproj`, etc.) o en sus archivos de configuración, verifica primero.
- **Trazabilidad:** Toda decisión técnica relevante debe estar vinculada a un ADR (Architectural Decision Record).
- **Calidad:** Ningún código se considera "completado" sin su correspondiente test, usando el framework de pruebas ya establecido en el proyecto (o el estándar de facto del lenguaje/stack si aún no existe uno).
- **Estándar:** Se prioriza el rendimiento y la seguridad apropiados al stack y dominio del proyecto (p. ej. control de acceso a datos, cifrado en reposo/tránsito, validación de entradas), aplicando las mejores prácticas reconocidas para la tecnología en uso — no una stack fija.

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
- Toda decisión técnica que se aleje de los estándares definidos debe documentarse como una **"Deuda Operativa"** en `docs/DEBT.md` (fuente única) con ID único, responsable y fecha objetivo. Colisión de IDs = fallo bloqueante.

## 5. Auditorías bajo Contrato C2 (G-2)
- Toda auditoría/cierre de fase requiere contrato C2 con criterios verificables.
- El % de completitud se **prueba por checklist**, nunca se declara (lección I-01).
- Evidencia obligatoria: comando + salida real + commit. Lo no verificable → BLOCKED_BY_ENVIRONMENT.
- Reporte de verificación en `docs/verification/` por fase (GOVERNANCE §16).

## 5. Aplicabilidad Multi-Stack
- Este protocolo (secciones 1-4) es el mismo para **todo proyecto**, sin importar el lenguaje, framework, runtime o proveedor de infraestructura.
- Los detalles específicos de una tecnología concreta (comandos de test, convenciones de estilo, estructura de carpetas, herramientas de build, etc.) **no pertenecen a este documento**: deben vivir en el `README.md`, `CONTRIBUTING.md` o el archivo de configuración/instrucciones propio de cada proyecto (p. ej. `CLAUDE.md`, `AGENTS.md`).
- Ante cualquier ambigüedad entre este documento y las convenciones locales de un proyecto, **el flujo de estados (Sección 2) y los principios (Secciones 1, 3 y 4) prevalecen**; los detalles de implementación se adaptan al stack local.


## LOGS ESTRUCTURADOS
console.log no es un sistema de logs.
Necesitas logs estructurados (formato JSON) con marcas de tiempo, IDs de usuario e IDs de petición.
Sin esto, depurar un problema en producción es como buscar una aguja en un pajar… con los ojos vendados.
Herramientas: Winston, Pino, Datadog, Papertrail (estas son ejemplos) buscar siempre opciones opensource 100%

## MONITOREO DE ERRORES
Debes saber cuándo algo falla ANTES de que tus usuarios te lo digan.
Configura un monitoreo de errores en tiempo real que capture stack traces, contexto del usuario y frecuencia.
Herramientas: Sentry, Rollbar, Bugsnag (estas son ejemplos) buscar siempre opciones opensource 100%

## RATE LIMITING EN TODOS LOS ENDPOINTS PÚBLICOS
Toda ruta expuesta al público necesita rate limiting.
Sin esto, un solo usuario malintencionado (o un bot) puede tirar todo tu sistema.
Protege: inicio de sesión, registro, recuperación de contraseña, búsqueda y cualquier endpoint de tu API.

## ENDPOINTS DE HEALTH CHECK
Tu infraestructura necesita una forma de saber si tu aplicación sigue viva.
Agrega una ruta /health que verifique: conexión a la base de datos, conexión al caché y dependencias críticas.
Sin esto, tu balanceador de carga puede enviar tráfico a un servidor que ya está caído.

## PLAN DE ROLLBACK
¿Qué pasa si tu nuevo despliegue rompe todo?
¿Sabes cómo volver a la versión anterior en menos de 5 minutos?
Si no, estás a un mal despliegue de una noche muy larga.
Configura: despliegues versionados, blue-green deployments o feature flags.

## CALENDARIO DE ROTACIÓN DE SECRETOS
Las claves de API y las contraseñas de bases de datos no deberían durar para siempre.
Programa un recordatorio para rotar todas las credenciales cada 90 días.
Y asegúrate de que esa rotación no requiera tiempo de inactividad.
