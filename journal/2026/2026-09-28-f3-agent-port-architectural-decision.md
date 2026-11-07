# 2026-09-28 — F3 port conflict closure attempt (prompt `correccion_38.md`)

## Propósito

Cerrar exclusivamente el hallazgo F3 de `correccion_37.md` (conflicto 8080
entre frontend `127.0.0.1:8080` y `linux-agent` `0.0.0.0:8080`, con
`AGENT_HEALTH_PORT` declarado en el launcher pero ignorado por el agente).
Sin Sprint 13, sin features, sin Framework, sin settings remotos, sin
U6a/U6b/U7, sin contenido comercial. `AUTHORIZE_COMMIT`/`AUTHORIZE_PUSH`
ausentes → sin commit, sin push.

## Baseline (FASE 0 — verificado tras `git fetch --prune`)

- **Monitor**: `HEAD = origin/main = ls-remote =
  e32fb883dc6c415d2baeb646d7a99ed24e04b898`; branch `main`; ahead/behind
  0/0; U6a `7ca822d…`, U6b `079024e…`, U7 `65f528f…` = ancestros ✓.
- **CI previa**: run `36463979777` sobre `e32fb883` = success (2/2) ✓.
- **Worktree preexistente registrado y preservado** (correccion_37, sin
  commit por autorización ausente): ` M start.sh`, ` M stop.sh`,
  `?? journal/2026/2026-09-28-production-readiness-governance-audit.md`.
- **Framework**: `HEAD = origin/main = ls-remote =
  381f56cfa48d092f85846e160d2e1fe6878f9f6f`; 9 entradas preexistentes
  intactas; journal Framework = 0 escrituras ✓.

## F3 original (de correccion_37, reproducido en vivo allí)

Arranque real del agente con el frontend corriendo →
`OSError: [Errno 98] … bind on address ('0.0.0.0', 8080): address already
in use`, rc=1. Frontend añadido en `249f475` (2026-09-16) DESPUÉS de los
specs del agente (`0be8241`, 2026-08-23) y de la tabla de puertos del
contrato (`02ed143`, 2026-08-30) — la colisión nació sin actualizar el
contrato.

## Evidencia del contrato `AGENT_HEALTH_PORT` (FASE 1, respuestas A–J)

- **A/B. Existe formalmente**: SÍ — en los specs del launcher de Monitor:
  `start.sh:50` y `stop.sh:29` (campo `port_env` del formato
  `name|app_dir|port_env|default_port` →
  `linux-agent|apps/agents/linux-agent|AGENT_HEALTH_PORT|8080`),
  introducido en `0be8241`, presente en TODAS las ramas (único valor de la
  historia: `8080`). NO existe en Framework (0 refs en todo
  `company-os-main`, incl. `.github`), ni en `.env`, ni en `.env.example`,
  ni en el código del agente, ni en tests, ni en docs.
- **C. Consumidor previsto**: el proceso `linux-agent`
  (`apps/agents/linux-agent/src/main.py` → `HealthServer.start`) — ese es
  el gap: el launcher calcula la URL de espera con
  `${AGENT_HEALTH_PORT:-8080}` (`start.sh:255,302`) pero el proceso
  ignora el entorno (`health.py:21-24` hardcodea `port: int = 8080`;
  `main.py` llama `await health.start()` sin argumento). Precedente
  obligado: los 12 servicios consumen su `*_HEALTH_PORT`
  (`collector-service/src/main.py:27` → `int(os.getenv("HEALTH_PORT",
  "8090"))`).
- **D/E. Default**: `8080`, definido por **Monitor** (specs del launcher +
  `cognitive_contract.md:124` §"Puertos del Sistema":
  `8080: Linux Agent`), no por Framework, no por configuración de
  despliegue (`.env`/`.env.example` no lo declaran, a diferencia de los 12
  puertos de servicio).
- **F. Frontend en 8080**: intencional a nivel contenedor
  (`apps/web/nginx.conf:19 listen 8080`, `Dockerfile EXPOSE 8080`) y como
  publicación host desde `249f475`, endurecida a loopback en `e32fb88`
  (correccion_34, cambio autorizado) y fijada por `correccion_38` FASE 3.1
  (`127.0.0.1:8080` debe seguir funcionando). El frontend NO tiene entrada
  en la tabla de puertos del contrato.
- **G. Bind `0.0.0.0` del agente**: mismo patrón de los 12 servicios
  (`TCPSite(…, "0.0.0.0", port)` en todos los `health.py`); el launcher
  solo sonda `127.0.0.1` → no es accidental ni exclusivo del agente; fuera
  de alcance (FASE 6 / observación LAN preexistente intacta).
- **H. Dependencias**: `start.sh` (`wait_health` + impresión de endpoints)
  y `stop.sh` (port-agnóstico, por pidfile) únicamente. El gateway solo
  monitorea 8090–8100; frontend/CI/tests no consumen la URL del agente.
- **I. Tests del contrato**: ninguno existente referenciaba
  `AGENT_HEALTH_PORT`/8080 del agente.
- **J. Referencias a mantener coherentes**: `start.sh:13` (comentario
  `(:8080)`), `start.sh:50`, `stop.sh:29`, `cognitive_contract.md:124`,
  entrada faltante en `.env`/`.env.example`, mención histórica
  `docs/frontend/architecture.md:518`.
- Búsqueda exhaustiva de un puerto alternativo para el agente: Framework,
  `.env`/`.env.example`, historial completo (`git log -S`), todas las
  ramas (`git grep` sobre todas), issues/PRs de GitHub, docs, ADRs →
  **cero resultados**: el único puerto jamás definido para el linux-agent
  es `8080` (familia de agentes: windows=8081, vmware=8082 en código, no
  aplicables a este host ni en la tabla del contrato).

## Decisión técnica (FASE 2): OPCIÓN B — `ARCHITECTURAL DECISION REQUIRED`

El mecanismo `AGENT_HEALTH_PORT` existe y está claro (condición de
OPCIÓN A), **pero cerrar F3 exige un valor efectivo ≠ 8080** y ningún
origen existente lo define:

- FASE 3.1 fija el frontend en `127.0.0.1:8080` y FASE 3.2 exige que el
  agente arranque sin conflicto → el agente NO puede escuchar en 8080.
- El único valor documentado (`8080`, `cognitive_contract.md:124` +
  specs) es exactamente el que colisiona; asignar un valor nuevo sería
  **inventar un puerto** (Regla 6) y una decisión unilateral de
  reasignación de la tabla de puertos (Regla 16 / FASE 2B: "NO inventar
  un puerto. NO elegir unilateralmente mover frontend o agente. NO
  modificar arquitectura.").
- La propia FASE 4 es inexecutable sin ese valor: 4.B ("el puerto frontend
  8080 no colisiona con el agente") y 4.E requieren un puerto definido
  por la arquitectura; FASE 5 (boot normal sin `address already in use`)
  tampoco pasaría.
- Por tanto: **sin código, sin tests, sin commit** (FASE 2B/FASE 7:
  "registrar esa conclusión; no modificar código relacionado
  innecesariamente").

### Decisión que falta (exactamente)

Definir el **puerto efectivo del `linux-agent`** cuando el frontend
retiene `127.0.0.1:8080`, y enmendar en consecuencia la tabla
`### Puertos del Sistema` de `cognitive_contract.md`.

### Dos alternativas (para el dueño)

1. **Reasignar al agente** (recomendada, cierra F3): elegir un puerto
   libre del sistema (la tabla documenta 8080–8102; el siguiente libre es
   `8103`; sin reservas documentadas en ninguna parte), declararlo
   `AGENT_HEALTH_PORT` en `.env`/`.env.example`, implementar en el agente
   el consumo del entorno (eliminar el hardcode de `health.py:21-24`,
   patrón idéntico al de los servicios), actualizar specs/comentario/tabla
   del contrato, y añadir los tests FASE 4.
2. **Reasignar al frontend** (excluida por esta tarea): mover la
   publicación host del nginx a otro puerto loopback y dejar al agente en
   el `8080` que le asigna el contrato — contradice FASE 3.1 de
   `correccion_38`.

## Archivos modificados / diff conceptual (FASE 3–4, 8)

- **Ningún archivo de código/configuración modificado por esta tarea.**
- Diff de esta tarea = **UNA sola entrada append-only de journal** (este
  archivo). Preservados intactos los cambios preexistentes de
  correccion_37 (`start.sh`, `stop.sh`, su journal) y todo lo rastreado.

## Validación (FASE 5) y seguridad (FASE 6)

- Sin estado modificado por esta tarea → batería de gates N/A; integridad
  del estado preservado verificada: `git diff --check` OK,
  `bash -n start.sh stop.sh` OK; los gates de correccion_37 sobre ese
  mismo estado quedaron en 766/766 (run de la tarea previa), sin
  regresiones porque esta tarea no tocó código.
- Runtime F3 sin modificar: el conflicto sigue reproducible tal cual fue
  evidenciado en correccion_37 (agente → EADDRINUSE con frontend en 8080;
  workaround `./start.sh --no-agent` boot limpio).
- Seguridad: sin cambios de red/exposición, sin secretos, sin relajación
  JWT/CORS/CSP/permisos, sin nuevo source of truth, Framework no
  contradicho (Framework: 0 refs, 0 escrituras).
- Limitaciones externas conservadas (sin tocar): code scanning ausente,
  validity checks de secretos deshabilitados, flags de branch protection,
  0 tags de release, servicios host en `0.0.0.0` (observación LAN),
  conflicto F3 abierto a la espera de la decisión.

## Controles

- Contenido comercial: 0 · Secretos: 0 · SHAs futuros: 0 ·
  Framework modificado: NO · Journal del Framework: 0 escrituras ·
  U6a/U6b/U7 intactos · journals históricos intactos ·
  commit/push: NO (autorizaciones ausentes).
