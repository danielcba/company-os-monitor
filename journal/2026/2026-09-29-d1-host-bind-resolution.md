# D1 Host Bind Resolution — 2026-09-29

## Baseline

- Monitor SHA real: `446dd36f6c74b99958261e33a5bc073a632ee1f4`
  (parent `eb686e2ec5e06f8b9771e1a3dd56739ff6d631ce`); `HEAD = origin/main =
  ls-remote`, ahead/behind `0 0`, staged `0` antes de esta tarea.
- CI baseline: run `36636544200`, head `446dd36…`, `completed/success`
  (`lint-and-test (3.12, 24)` = success, `docker-build` = success).
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` triple-match,
  0 writes al journal del Framework.

## Problema D1

La auditoría previa (`2026-09-29-release-governance-decision-audit.md`)
clasificó como `ARCHITECTURAL DECISION` el bind `0.0.0.0` de los servicios
host-native: exposición LAN innecesaria (la UI y todo el perímetro compose ya
son loopback) sin ningún consumidor legítimo fuera del host.

## Decisión arquitectónica (adoptada por esta tarea)

Los **14 servicios host-native** (SERVICE_SPECS de `start.sh` + linux-agent,
puertos **8090-8103**) deben escuchar exclusivamente en **`127.0.0.1`**:

1. Todos los consumidores verificados son host-locales.
2. No hay necesidad funcional actual de acceso LAN.
3. `0.0.0.0` genera superficie de red innecesaria.
4. Compose ya publica solo loopback (`127.0.0.1:8080/5433/6379`, precedente
   commit `e32fb88`).
5. El cambio elimina la exposición LAN sin tocar consumidores.
6. Una variable `HOST` configurable añadiría complejidad/superficie de
   configuración innecesaria para el topology actual → **no se introduce**.
7. Un futuro escenario de agentes remotos requiere una decisión arquitectónica
   explícita futura; hoy no se mantiene exposición LAN sin uso.

## Evidencia estática (antes del cambio)

- 14 `TCPSite(..., "0.0.0.0", …)` en: collector, context, pattern, anomaly,
  hypothesis, confidence, recommendation, decision, report, insight,
  evaluation, user, gateway, linux-agent.
- Consumidores: gateway `DEFAULT_SERVICE_HEALTH` → `http://localhost:8090–8099`;
  navegador `client.ts`/`.env.development` → `http://localhost:8100` y
  `http://localhost:8099`; probes de `start.sh` → `http://127.0.0.1:$port/health`.
- Sin service discovery, sin `proxy_pass` (nginx del frontend es SPA estática),
  sin `host.docker.internal`, sin integración que use la IP del host, sin
  consumidor remoto. Frontend loopback-only.

## Evidencia runtime (antes y después)

- Antes (baseline): `ss -ltn` → `0.0.0.0:8090…8103`; IP LAN
  `192.168.100.64` respondía `HTTP 200` en 8100/8099/8103 (y familia); el
  frontend en `127.0.0.1:8080` ya rechazaba LAN.
- Después (mismo host, stack real): `start.sh` rc=0; `ss -ltn` →
  `127.0.0.1:8090…8103` (14/14) y `127.0.0.1:8080`; loopback `HTTP 200`
  **14/14**; LAN `192.168.100.64` → **14/14 ConnectionRefused**, 0 fugas,
  frontend también rechazado; smoke de gateway intacto (preflight CORS 200 +
  ACAO exacto, GET 200 + ACAO, 401 + ACAO en observations, preflight de login
  de user-service 200 + ACAO, origen denegado sin ACAO). `stop.sh` rc=0;
  estado restaurado (solo postgres).

## Alcance exacto

Modificados (solo D1):

- `apps/services/{collector,context,pattern,anomaly,hypothesis,confidence,recommendation,decision,report,insight,user}-service/src/health.py`
- `apps/services/evaluation-service/src/main.py`
- `apps/gateway/api-gateway/src/health.py`
- `apps/agents/linux-agent/src/health.py`
- `bandit.yaml` — solo el rationale de B104 (ver abajo)
- `tests/architecture/test_d1_loopback_bind.py` — nuevo (21 tests)
- `journal/2026/2026-09-29-d1-host-bind-resolution.md` — esta entrada

NO modificado (declarado y verificado):

- `apps/agents/windows-agent/src/health.py` y
  `apps/agents/vmware-agent/src/health.py` siguen con `0.0.0.0`: **fuera de los
  14 enumerados** y **nunca los arranca `start.sh`** (pin de test incluido);
  no abren socket en este host. Corregirlos pertenece a la futura decisión de
  agentes remotos. Si alguien los añade a `start.sh` sin corregir el bind, el
  test `test_excluded_agents_are_never_launched` falla.
- `.env.example`: la observación `INSIGHT_HEALTH_PORT` (8101) es una
  inconsistencia documental real pero **no forma parte del bind topology D1**
  → queda fuera de este diff como `RECOMMENDATION` pendiente.
- Rutas/API/lógica/auth/JWT/Redis/Postgres/gateway/frontend/CORS/compose:
  sin cambios. `start.sh`/`stop.sh` y los journals históricos: preexistentes,
  intactos, sin staged.

## Tests

Nuevo `tests/architecture/test_d1_loopback_bind.py` (21 tests, todos PASS):

1. Bind loopback + ausencia de `0.0.0.0` en los 14 archivos (parametrizado).
2. Inventario de lanzador = exactamente los 14 servicios, puertos 8090-8103.
3. Probes de `start.sh` solo `127.0.0.1`; consumidores del gateway/navegador
   siguen host-local; publicaciones compose siguen loopback.
4. Pin de alcance: windows/vmware-agent fuera de `start.sh`.
5. Runtime: arranca el `linux-agent` real en puerto libre → `/health` en
   loopback 200, LISTEN socket a nivel OS en `127.0.0.1` (`/proc/net/tcp`),
   e interfaz no-loopback **rechazada**.

Validación completa (estado final): `git diff --check` PASS; YAML 0 inválidos;
`ruff check .` All checks passed; `mypy libs/` Success (70 archivos);
mypy CI-style gateway Success (22) y user-service Success (8);
`bandit -r apps/ libs/ -ll -c bandit.yaml` rc=0 (High 0 / Medium 0; total de
bajísima severidad 1812 = línea base, sin nuevos hallazgos);
`compileall` OK; `pytest tests/` **799 passed** (778 + 21 nuevos);
`pytest tests/security tests/architecture` **354 passed**; suite gateway
**158 passed, 1 skipped** (skip preexistente); user-service **62 passed**;
CORS **12 + 7** (cada suite por separado; ejecutarlas en el mismo proceso
colisiona por nombre de módulo `test_cors.py`/`src` — preexistente, CI las
corre en procesos separados); frontend lint 0 errores, typecheck OK, vitest
**182 passed**; `docker compose config` OK; boot rc=0, matriz de runtime
arriba, stop rc=0. Sin skips ni xfails nuevos.

## Resultado

- Exposición LAN en 8090-8103: **BLOCKED** (14/14 refused).
- Consumidores host-local: **PRESERVED** (14/14 loopback 200, smoke CORS/auth
  intacto, suites completas verdes).
- D1 → decidido, implementado y testeado. Commit/push NO realizados:
  `AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO` en esta operación.

## Limitación futura

Cualquier acceso a estos servicios desde otra máquina (agente remoto, operador
remoto, reverse proxy externo) exige una **decisión arquitectónica explícita
futura** (p. ej. variable `HOST` o publicación selectiva); no se reintroduce
exposición LAN implícita.
