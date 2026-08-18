# Company OS Monitor - Plan Maestro de Diseño

## Visión General

# COS-Monitor (Company OS Monitor)

Plataforma SaaS para monitoreo, análisis y diagnóstico automático de infraestructura IT para DataCenters usando IA local (LM Studio) y componentes Open Source. Todas las funcionalidades, datos, pantallas que se muestren deben estar estrictamente condicionadas por el framework de arquitectura cognitiva https://github.com/danielcba/company-os/, este repositorio público no debe ser modificado, solo usar en modo lectura. También puedes acceder a el a través del path: '/home/dcordoba/Documents/Default Project/company/company-os-main/' este es un clon del proyecto original.
El proyecto debe soportar el agregado de funcionalidades sin afectar el funcionamiento general de la plataforma.

---

# FASE 1: 

## Funcionalidades Mínimas
1. Recolección de métricas de servidores Linux (CPU, RAM, Disco)
2. Recolección de métricas de Windows Server vía WMI (CPU, RAM, Disco, Eventos críticos)
3. Dashboard web básico con estado actual
4. Sistema de alertas
5. Generación de informe PDF ejecutivo básico
6. Autenticación multi-tenant (un administrador por cliente)

## Arquitectura MVP
- Backend: Python/FastAPI — arquitectura de microservicios
- Frontend: HTML + HTMX + Tailwind CSS
- Base de datos: PostgreSQL
- Cache: Redis
- Contenedorización: Docker + Docker Compose
- Recolección: Agentes Python SSH + WMI remoto
- Comunicación: REST/HTTP + eventos asíncronos
- API Gateway: Nginx/Traefik/Kong


## Dependencias
```
fastapi, uvicorn, sqlalchemy, asyncpg, redis,
psutil (agentes Linux), pywinrm (WMI remoto),
cryptography, httpx, jinja2, weasyprint (PDF),
pandas, scikit-learn, openai (API compatible LM Studio),
docker, pytest, alembic
```

## Riesgos
1. WMI remoto requiere configuración de red y permisos en Windows
2. LM Studio puede necesitar GPU para inferencia rápida
3. PyMEs pueden no tener infraestructura standardizada
4. Adopción de agentes remotos requiere apertura de puertos

---

# FASE 2: Arquitectura Completa

## Diagrama Lógico
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INFRASTRUCTURE LAYER                              │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Linux Agent  │  │ Windows      │  │ VMware Agent │  │ Network      │   │
│  │              │  │ Agent        │  │              │  │ Agent        │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                 │                 │                 │             │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          └─────────────────┴─────────────────┴─────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION LAYER                                │
│                                                                             │
│  ┌────────────────┐     ┌──────────────────┐     ┌────────────────────┐    │
│  │  API Gateway   │     │ Webhook Handler  │     │ Kafka / RabbitMQ   │    │
│  │                │     │                  │     │    Event Bus       │    │
│  └───────┬────────┘     └────────┬─────────┘     └──────────┬─────────┘    │
│          │                       │                          │              │
│          └───────────────────────┴──────────────────────────┘              │
│                                  │                                         │
└──────────────────────────────────┼─────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MICROSERVICES LAYER                               │
│                                                                             │
│  ┌────────────────┐     ┌────────────────┐     ┌────────────────┐          │
│  │    COLLECTOR   │     │    PREDICTOR   │     │    ANALYZER    │          │
│  │    SERVICE     │     │    SERVICE     │     │    SERVICE     │          │
│  │    FastAPI     │     │    FastAPI     │     │    FastAPI     │          │
│  └───────┬────────┘     └───────┬────────┘     └───────┬────────┘          │
│          │                       │                      │                   │
│          ▼                       ▼                      ▼                   │
│  ┌────────────────┐     ┌────────────────┐     ┌────────────────┐          │
│  │ Collector DB   │     │ Predictor DB   │     │ Analyzer DB    │          │
│  │ PostgreSQL /   │     │ PostgreSQL     │     │ PostgreSQL     │          │
│  │ TimescaleDB    │     │                │     │                │          │
│  └────────────────┘     └────────────────┘     └────────────────┘          │
│                                                                             │
│                              │                                              │
│                              ▼                                              │
│                     ┌────────────────────┐                                  │
│                     │     LLM SERVICE    │                                  │
│                     │      FastAPI       │                                  │
│                     │                    │                                  │
│                     │  Model Abstraction │                                  │
│                     └─────────┬──────────┘                                  │
│                               │                                             │
│                               ▼                                             │
│                    ┌──────────────────────┐                                 │
│                    │   LLM Runtime        │                                 │
│                    │                      │                                 │
│                    │ LM Studio / Ollama / │                                 │
│                    │ vLLM / External API  │                                 │
│                    └──────────────────────┘                                 │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │                    REPORT GENERATOR                          │           │
│  │                         FastAPI                              │           │
│  └────────────────────────────┬─────────────────────────────────┘           │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                     │
│                                                                             │
│  ┌──────────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │ PostgreSQL /         │    │   Redis Cache    │    │  Object Storage  │  │
│  │ TimescaleDB          │    │                  │    │  MinIO / S3      │  │
│  │                      │    │                  │    │                  │  │
│  │ Persistent Data      │    │ Cache / Sessions │    │ Reports / Files  │  │
│  │ Time-Series Data     │    │ Queues / State   │    │ Models / Artifacts│  │
│  └──────────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Microservicios
1. **api-gateway**: Nginx/Traefik + FastAPI - autenticación, rate limiting
2. **collector-service**: Recibe métricas de agentes, las normaliza y almacena
3. **predictor-service**: Modelos estadísticos y ML para predicciones
4. **analyzer-service** (LM Studio): Análisis IA de eventos y tendencias
5. **report-service**: Generación de informes PDF/HTML
6. **alert-service**: Evaluación de reglas de alerta + notificaciones
7. **agent-manager**: Registro, configuración y health-check de agentes
8. **user-service**: Gestión de usuarios, tenants, roles

## Esquema de Base de Datos

### Tabla: tenants
- id UUID PK
- name VARCHAR(255)
- slug VARCHAR(100) UNIQUE
- plan VARCHAR(50) (basic/pro/enterprise)
- settings JSONB
- created_at TIMESTAMPTZ
- updated_at TIMESTAMPTZ

### Tabla: servers
- id UUID PK
- tenant_id UUID FK → tenants
- hostname VARCHAR(255)
- ip_address INET
- os_type VARCHAR(50) (linux/windows/vmware)
- os_version VARCHAR(100)
- agent_version VARCHAR(50)
- status VARCHAR(20) (online/offline/unknown)
- last_seen TIMESTAMPTZ
- metadata JSONB
- created_at TIMESTAMPTZ
- Índices: (tenant_id, status), (tenant_id, os_type), (last_seen)

### Tabla: metrics
- id BIGSERIAL PK
- server_id UUID FK → servers
- metric_type VARCHAR(50) (cpu/ram/disk/network/log)
- metric_name VARCHAR(100)
- value DOUBLE PRECISION
- unit VARCHAR(20)
- tags JSONB
- timestamp TIMESTAMPTZ NOT NULL
- Índices: (server_id, metric_type, timestamp DESC), (metric_type, timestamp DESC) - particionado por mes

### Tabla: events
- id BIGSERIAL PK
- tenant_id UUID FK → tenants
- server_id UUID FK → servers
- event_type VARCHAR(50) (error/warning/info/critical)
- source VARCHAR(100) (event_log/service/log_file)
- title VARCHAR(500)
- description TEXT
- raw_data JSONB
- severity INTEGER (1-5)
- ai_analyzed BOOLEAN DEFAULT FALSE
- ai_summary TEXT
- timestamp TIMESTAMPTZ NOT NULL
- Índices: (tenant_id, event_type, timestamp DESC), (server_id, timestamp DESC), (severity, ai_analyzed)

### Tabla: predictions
- id BIGSERIAL PK
- server_id UUID FK → servers
- metric_type VARCHAR(50)
- predicted_metric VARCHAR(100)
- current_value DOUBLE PRECISION
- predicted_value DOUBLE PRECISION
- prediction_date DATE
- confidence DOUBLE PRECISION (0-1)
- days_to_threshold INTEGER
- threshold_value DOUBLE PRECISION
- model_used VARCHAR(100)
- features JSONB
- created_at TIMESTAMPTZ
- Índices: (server_id, metric_type, prediction_date), (days_to_threshold)

### Tabla: reports
- id UUID PK
- tenant_id UUID FK → tenants
- report_type VARCHAR(50) (executive/technical/compliance)
- title VARCHAR(500)
- summary TEXT
- content JSONB
- ai_generated BOOLEAN DEFAULT TRUE
- model_used VARCHAR(100)
- period_start DATE
- period_end DATE
- generated_at TIMESTAMPTZ
- file_path VARCHAR(500)
- Índices: (tenant_id, report_type, period_end DESC)

### Tabla: alerts
- id UUID PK
- tenant_id UUID FK → tenants
- server_id UUID FK → servers
- rule_id UUID FK → alert_rules
- status VARCHAR(20) (triggered/acknowledged/resolved)
- severity VARCHAR(20) (info/warning/critical)
- title VARCHAR(500)
- message TEXT
- triggered_value DOUBLE PRECISION
- threshold_value DOUBLE PRECISION
- notified_at TIMESTAMPTZ[]
- resolved_at TIMESTAMPTZ
- created_at TIMESTAMPTZ
- Índices: (tenant_id, status, severity), (server_id, status)

### Tabla: alert_rules
- id UUID PK
- tenant_id UUID FK → tenants
- name VARCHAR(255)
- metric_type VARCHAR(50)
- condition VARCHAR(10) (gt/lt/gte/lte/eq)
- threshold DOUBLE PRECISION
- duration_minutes INTEGER
- severity VARCHAR(20)
- enabled BOOLEAN DEFAULT TRUE
- notification_channels JSONB
- created_at TIMESTAMPTZ
- Índices: (tenant_id, enabled, metric_type)

## Estrategia de Crecimiento
- **Particionamiento**: metrics y events particionados por mes (PostgreSQL declarative partitioning)
- **TimescaleDB**: Para métricas de series temporales con compresión automática y retention policies
- **Read replicas**: Para dashboards y reportes
- **Cacheo**: Redis para métricas en tiempo real (últimos 5 minutos)
- **Archivo**: Datos > 12 meses movidos a objeto store (MinIO) como JSON/Parquet
- **Sharding**: Por tenant cuando se superen los 500+ tenants

---

# FASE 3: Motor de Recolección

## Windows (WMI Remoto + WinRM)

### Eventos Críticos
```
WQL: SELECT * FROM Win32_NTLogEvent WHERE Type = 'Error' OR Type = 'Critical'
Librería: pywinrm + wmi (Python)
Frecuencia: Cada 5 minutos
```

### Servicios Detenidos
```
WQL: SELECT * FROM Win32_Service WHERE State = 'Stopped' AND StartMode = 'Auto'
```

### Usuarios Bloqueados/Inactivos
```
PowerShell Remoto: Search-ADAccount -LockedOut | -Inactive (Days:$days)
```

### Consumo Recursos
```
WQL:
- CPU: Win32_PerfFormattedData_PerfOS_Processor (% Processor Time)
- RAM: Win32_OperatingSystem (FreePhysicalMemory, TotalVisibleMemorySize)
- Disco: Win32_LogicalDisk (FreeSpace, Size)
```

## Active Directory (LDAP + PowerShell)

### Consultas Clave
```python
# Usuarios inactivos (90+ días sin login)
(LastLogonTimestamp < (Now - 90d)) AND (Enabled = TRUE)

# Contraseñas próximas a vencer
(PasswordLastSet < (Now - $maxPwdAge + 14d))

# Grupos privilegiados
Members of: Domain Admins, Enterprise Admins, Schema Admins
```

## VMware (vSphere API - pyVmomi)

### Consultas Clave
```python
# Snapshots antiguos (>7 días)
snapshot.create_time < (now - 7d)

# Datastores llenos (>85%)
datastore.summary.capacity * 0.85 >= datastore.summary.freeSpace

# VMs apagadas
vm.runtime.powerState != 'poweredOn'

# Tendencias de crecimiento
vm_stats = collect_historical(vm, 'disk.usage.average', days=30)
```

## Backup (Veeam - REST API)
```
GET /api/backups/{id}/points
GET /api/jobs/{id}/laststatus
Frecuencia: Cada hora post-ventana de backup
```

## Redes (Nmap + SNMP)
```bash
# Descubrimiento automático
nmap -sS -T4 -O -oX output.xml 10.0.0.0/24

# SNMP Walk para switches
snmpwalk -v2c -c public 10.0.0.1 1.3.6.1.2.1.2.2

# Cambios de puertos: diff de estado 15 min vs actual
```

### Arquitectura de Agentes
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Agent       │────▶│  Collector   │────▶│  PostgreSQL  │
│  (Python)    │     │  Service     │     │  (Timescale) │
│              │◀────│              │◀────│              │
│ - Recopila   │     │ - Valida     │     │ - Almacena   │
│ - Cachea     │     │ - Normaliza  │     │ - Retención  │
│ - Envía      │     │ - Enruta     │     │ - Archiva    │
└──────────────┘     └──────────────┘     └──────────────┘
```

---

# FASE 4: Motor Predictivo

## Algoritmos por Tipo de Predicción

### Saturación de Discos
- **Modelo**: Holt-Winters (triple suavizado exponencial) con estacionalidad semanal
- **Alternativa**: Prophet (Facebook) para patrones no lineales
- **Métrica**: `disk_usage_percent` forecast a 30/60/90 días
- **Librería**: `statsmodels` + `prophet`

### Falta de Memoria
- **Modelo**: ARIMA (AutoRegressive Integrated Moving Average)
- **Métrica**: `memory_usage_percent` + `swap_usage`
- **Librería**: `pmdarima` (auto_arima para selección automática de parámetros)

### Crecimiento de Logs
- **Modelo**: Regresión lineal segmentada (piecewise linear regression)
- **Métrica**: `log_size_bytes` por servicio/día
- **Librería**: `scikit-learn` + `numpyro` (Bayesian changepoint detection)

### Crecimiento de Bases de Datos
- **Modelo**: Random Forest Regressor + feature engineering
- **Features**: día_semana, mes, crecimiento_histórico, transacciones_por_hora
- **Librería**: `scikit-learn` + `feature_engine`

### Capacidad de Almacenamiento
- **Modelo**: XGBoost + LSTM (ensemble)
- **Features múltiples**: uso_actual, tasa_crecimiento, compresión, backups
- **Librería**: `xgboost` + `tensorflow` (opcional)

## Pipeline de ML
```
raw_data → feature_engineering → model_selection → training → evaluation → prediction → alert
```

## Modelos Estadísticos vs ML vs DL
| Tipo | Algoritmo | Datos necesarios | Precisión | Costo |
|------|-----------|-----------------|-----------|-------|
| Estadístico | Holt-Winters | 30 días | 80-85% | Muy bajo |
| Estadístico | ARIMA/SARIMA | 60 días | 85-90% | Bajo |
| ML | Random Forest | 90 días | 88-93% | Medio |
| ML | XGBoost | 90 días | 90-95% | Medio |
| DL | LSTM | 180+ días | 92-97% | Alto |

## Estrategia de Predicción
1. **Corto plazo** (7 días): Holt-Winters / ARIMA - rápido, bajo costo
2. **Medio plazo** (30 días): Prophet / Random Forest - balance precisión/costo
3. **Largo plazo** (90+ días): XGBoost ensemble - mayor precisión, más datos
4. **Fallback**: Promedio móvil ponderado si hay < 7 días de datos

---

# FASE 5: LM Studio - IA Local

## Modelos Recomendados

| Modelo | Tamaño | RAM Mínima | RAM Recomendada | Uso | Licencia |
|--------|--------|-----------|-----------------|-----|----------|
| **Qwen 3 14B** (Q4) | 9 GB | 12 GB | 16 GB | Análisis de logs - general | Apache 2.0 |
| **Qwen 3 32B** (Q4) | 19 GB | 24 GB | 32 GB | Análisis complejo - premium | Apache 2.0 |
| **DeepSeek V3** (Q4_K_M) | ~22 GB activos | 24 GB | 32 GB | Razonamiento - mejores conclusiones | MIT |
| **DeepSeek R1 32B** (Q4) | ~19 GB | 24 GB | 32 GB | Diagnóstico técnico profundo | MIT |
| **Llama 4 8B** (Q4) | 4.9 GB | 8 GB | 16 GB | Análisis simple - menor hardware | Llama Community |
| **Llama 4 70B** (Q4) | 43 GB | 48 GB | 64 GB | Enterprise - mejor calidad | Llama Community |
| **Gemma 3 12B** (Q4) | 7.5 GB | 12 GB | 16 GB | Análisis técnico - Apple Silicon | Gemma |
| **Mistral 7B** | 4.4 GB | 8 GB | 16 GB | Análisis simple - budget | Apache 2.0 |

## Comparativa de Modelos para InfraDoctor

| Escenario | Modelo Recomendado | Justificación |
|-----------|-------------------|---------------|
| Análisis de eventos críticos (logs, errores) | Qwen 3 14B | Excelente comprensión, bajo HW |
| Diagnóstico de seguridad AD | DeepSeek R1 32B | Razonamiento superior para threat analysis |
| Generación de informes ejecutivos | Qwen 3 32B | Mejor redacción, formato estructurado |
| Detección de anomalías | DeepSeek V3 | Razonamiento causal, patrones complejos |
| Análisis de tendencias | Qwen 3 14B | Suficiente precisión, eficiente |
| MVP inicial | Llama 4 8B / Mistral 7B | Mínimo hardware requerido |

## Requerimientos de Hardware

### Mínimo (MVP - 3-5 clientes)
- CPU: 8 cores x86_64 (AVX2)
- RAM: 16 GB (sistema + modelo 7-8B)
- GPU: Opcional (CPU inference ~3-5 tok/s)
- Disco: 50 GB SSD + 20 GB modelos

### Recomendado (Producción - 20+ clientes)
- CPU: 16 cores o GPU NVIDIA RTX 3060+ (12 GB VRAM)
- RAM: 32 GB (sistema + modelo 14-32B)
- GPU: RTX 3090/4090 o 2x RTX 3060
- Disco: 100 GB NVMe + 50 GB modelos

### Enterprise (100+ clientes)
- GPU: 2x A4000 / RTX 6000 Ada (48+ GB VRAM)
- RAM: 64-128 GB
- Modelo: Llama 4 70B o DeepSeek V3

## Costos de Hardware

| Configuración | CPU | GPU | RAM | Costo Aprox. |
|--------------|-----|-----|-----|-------------|
| Budget | Xeon E5-2680 v4 | CPU only | 16 GB | $400-600 |
| Pro | Ryzen 9 7950X | RTX 3090 24GB | 32 GB | $2,500-3,500 |
| Enterprise | Dual EPYC | 2x A4000 48GB | 128 GB | $8,000-12,000 |
| Cloud GPU | - | A100 80GB | 64 GB | $2-5/hora |

## Integración con InfraDoctor

```python
from openai import OpenAI

# Cliente compatible con LM Studio
lm_client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed"
)

def analyze_events(events: list[str]) -> dict:
    response = lm_client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": format_events(events)}
        ],
        temperature=0.1,
        max_tokens=2000
    )
    return parse_response(response.choices[0].message.content)
```

---

# FASE 6: Informes Ejecutivos

## Generación Automática por IA

### System Prompt para Análisis
```
Eres un experto en infraestructura IT con 30+ años de experiencia.
Analiza los siguientes eventos y métricas de infraestructura:

1. Identifica problemas CRÍTICOS (riesgo inmediato)
2. Identifica problemas ALTOS (riesgo en 7-30 días)
3. Identifica problemas MEDIOS (riesgo en 30-90 días)
4. Identifica mejoras recomendadas

Para cada problema indica:
- Impacto en negocio (ej: "riesgo de pérdida de datos")
- Evidencia (log, métrica, evento)
- Recomendación técnica específica
- Prioridad (1-5)
```

### Resumen Ejecutivo (para Directivos)
```
Formato: 1 página máximo
Lenguaje: No técnico, orientado a negocio
Contenido:
- Salud general del sistema (verde/amarillo/rojo)
- Top 3 problemas críticos
- Top 3 riesgos futuros
- ROI de correcciones
```

### Resumen Técnico (para Administradores IT)
```
Formato: 5-10 páginas
Contenido:
1. Resumen ejecutivo técnico (1 párrafo)
2. Estado por servidor/servicio (tablas)
3. Eventos críticos con logs completos
4. Predicciones con gráficos
5. Recomendaciones priorizadas con comandos exactos
6. Evidencias adjuntas
```

### Ejemplo de Output
```json
{
  "executive_summary": "El servidor ERP presenta riesgo alto de saturación de disco en 14 días. Existen 23 usuarios inactivos en Active Directory. El backup de producción falló tres veces esta semana.",
  "health_score": 72,
  "critical": [
    {
      "title": "Saturación de disco - Servidor ERP",
      "days_to_critical": 14,
      "impact": "Detención del sistema ERP",
      "current_usage": "85%",
      "growth_rate": "2.3% semanal",
      "recommendation": "Expandir almacenamiento o purgar datos históricos pre-2019"
    }
  ],
  "risks": [
    {
      "title": "23 usuarios AD inactivos",
      "risk": "Riesgo de seguridad - cuentas huérfanas"
    }
  ],
  "predictions": [
    {
      "metric": "disk_usage",
      "server": "ERP-SRV-01",
      "current": 85,
      "predicted_30d": 94,
      "predicted_60d": 98,
      "threshold": 95
    }
  ]
}
```

---

# FASE 7: Seguridad

## Estrategia de Seguridad

### Cifrado
- **En tránsito**: TLS 1.3 (Let's Encrypt + cert-manager)
- **En reposo**: AES-256-GCM (PostgreSQL pgcrypto + aplicación)
- **Métricas**: Cifrado campo a campo para datos sensibles
- **Backups**: Cifrados con GPG antes de subir a objeto store

### Autenticación
- **Usuarios**: JWT (access 15min + refresh 7d) con RS256
- **OAuth2**: Google, Microsoft Entra ID (opcional Enterprise)
- **MFA**: TOTP (pyotp + qrcode) para cuentas admin
- **API Keys**: Hash SHA-256 almacenado, prefijo `idr_`
- **Rate Limiting**: 100 req/min por usuario, 10 req/min por API key

### Autorización (RBAC)
| Rol | Permisos |
|-----|----------|
| viewer | Ver dashboard, informes |
| operator | View + acknowledger alertas |
| admin | Full gestión del tenant |
| superadmin | Gestión multi-tenant |

### Gestión de Secretos
- HashiCorp Vault (producción) o python-dotenv (desarrollo)
- Rotación automática cada 90 días
- Auditoría de acceso a secretos

### Hardening
- Docker: no-root, read-only rootfs, seccomp, AppArmor
- PostgreSQL: SSL-only, pg_hba.conf restrictivo, roles mínimos
- API Gateway: WAF (ModSecurity), rate limiting, DDoS protection
- OS: Ubuntu LTS, automatic security updates, fail2ban, auditd

### Auditoría
```
Tabla: audit_log
- id UUID PK
- tenant_id UUID FK
- user_id UUID
- action VARCHAR(50) (login/create/update/delete/export)
- resource_type VARCHAR(50)
- resource_id UUID
- details JSONB (old_values, new_values)
- ip_address INET
- user_agent TEXT
- timestamp TIMESTAMPTZ

Política: Retención 3 años, inmutable (append-only)
```

### Cumplimiento Normativo

| Estándar | Controles implementados |
|----------|------------------------|
| ISO 27001 | A.9 (Control de acceso), A.10 (Cifrado), A.12 (Operaciones), A.16 (Incidentes) |
| CIS Controls | Control 1 (Inventario), Control 6 (Logs), Control 13 (Protección datos), Control 16 (Monitoreo) |
| NIST CSF 2.0 | IDENTIFY (Asset Management), PROTECT (Data Security), DETECT (Anomalies), RESPOND (Incidents) |

### Medidas Específicas por Estándar
- **ISO 27001 A.9.2.3**: MFA para accesos privilegiados
- **CIS 4.1**: Logs centralizados con retención > 12 meses
- **NIST PR.DS-1**: Cifrado AES-256 en reposo y TLS 1.3 en tránsito
- **ISO 27001 A.12.4.1**: Registro de eventos con protección contra manipulación
- **CIS 13.1**: Segmentación de red entre servicios

---

# FASE 8: Modelo Comercial

## Planes y Precios

| Característica | Básico | Profesional | Enterprise |
|---------------|--------|-------------|------------|
| Servidores monitoreados | Hasta 5 | Hasta 25 | Ilimitado |
| Tipos de entorno | Linux + Windows | Todos incl. VMware | Todos incl. custom |
| Retención de datos | 30 días | 90 días | 365 días |
| Alertas | Básicas (umbral) | Avanzadas (ML + IA) | Predictivas + IA |
| Informes ejecutivos | Semanal | Diario + On-demand | Tiempo real |
| LM Studio (IA local) | Análisis básico | Análisis completo | Análisis premium + custom |
| APIs | - | REST + Webhooks | REST + Webhooks + SDK |
| Soporte | Email 48h | Chat 24h + Email 12h | Dedicado + SLA 99.9% |
| Usuarios | 2 | 5 | Ilimitado |
| On-premise (self-host) | No | No | Sí |

### Precios Sugeridos

| Región | Básico | Profesional | Enterprise |
|--------|--------|-------------|------------|
| **Argentina** | ARS $15,000/mes | ARS $45,000/mes | ARS $120,000/mes |
| **Latinoamérica** | USD $29/mes | USD $89/mes | USD $249/mes |
| **Estados Unidos** | USD $49/mes | USD $149/mes | USD $499/mes |

### Justificación de Precios
- **Argentina**: Mercado con alta demanda pero menor poder adquisitivo. Typeform cuesta ~$60.000 ARS, Datadog ~$200.000 ARS. InfraDoctor es 25-50% más barato.
- **Latinoamérica**: Mercado SaaS creciendo 14.2% CAGR. Precios competitivos vs Datadog ($15/host/mes + fees) y New Relic ($0.55/GB). InfraDoctor es todo-incluido.
- **USA**: Precios premium para competir con Zabbix (gratis), PRTG ($1,700/licencia), LogicMonitor (~$300/mes). Diferenciación: IA local.

---

# FASE 9: Roadmap

## Primer Mes (Sprint 0-4)
**Objetivo:** MVP funcional con 1 cliente piloto
- [x] Setup de infraestructura (Docker, PostgreSQL, CI/CD)
- [x] Agente Linux (CPU, RAM, Disco)
- [x] Agente Windows vía WMI (eventos críticos + recursos)
- [x] Dashboard básico con métricas en tiempo real
- [x] Alertas por umbral (Email + Web)
- [x] Integración LM Studio con Mistral 7B
- [x] Documentación de instalación y despliegue

## Primer Trimestre (Sprint 5-12)
**Objetivo:** 5 clientes pagos
- [ ] Agente VMware (ESXi, Datastores, Snapshots)
- [ ] Active Directory (usuarios inactivos, passwords, grupos)
- [ ] Predicciones básicas (disco + RAM con ARIMA)
- [ ] Reportes ejecutivos semanales (PDF)
- [ ] Multi-tenancy completo
- [ ] Portal de clientes (login, configuración)
- [ ] LM Studio upgrade a Qwen 3 14B
- [ ] Backup Veeam (estado de jobs, tendencias)
- [ ] Plan Básico y Profesional activos

## Primer Semestre (Sprint 13-24)
**Objetivo:** 25 clientes, ARR $50k+
- [ ] Agente de red (nmap, SNMP, descubrimiento automático)
- [ ] Predicciones avanzadas (logs, BD, XGBoost)
- [ ] Anomaly detection con DeepSeek
- [ ] Reportes técnicos detallados
- [ ] Alertas predictivas (antes de que ocurra)
- [ ] LM Studio upgrade a Qwen 3 32B (GPU opcional)
- [ ] Integración Office365 / Exchange Online
- [ ] Webhooks y API pública
- [ ] MFA + RBAC completo
- [ ] Plan Enterprise
- [ ] Landing page + funnel de ventas funcionando

## Primer Año (Sprint 25-48)
**Objetivo:** 100+ clientes, ARR $250k+
- [ ] Agente Backup Exec / ArcServe
- [ ] Predicción LSTM (Deep Learning)
- [ ] LM Studio Enterprise (Llama 4 70B / DeepSeek V3)
- [ ] ISO 27001 - preparación para certificación
- [ ] SOC 2 Type II readiness
- [ ] On-premise deployment (Docker sellado)
- [ ] Marketplace de integraciones
- [ ] Partner program (MSPs)
- [ ] Versión white-label para consultores
- [ ] App mobile (estado + alertas)
- [ ] SLA 99.9% con multi-región
- [ ] $1M ARR target

---

# FASE 10: Backlog Priorizado por ROI

| # | Funcionalidad | Prioridad | Complejidad | Dependencias | Horas | ROI Esperado |
|---|--------------|-----------|-------------|--------------|-------|-------------|
| 1 | Agente Linux (CPU/RAM/Disco) | Crítica | Baja | Ninguna | 40 | Fundamental - sin esto no hay producto |
| 2 | Dashboard básico web | Crítica | Media | BD, Agentes | 60 | Fundamental - visualización mínima |
| 3 | Agente Windows vía WMI | Crítica | Media | Agente Linux | 60 | Atrae clientes con AD/Windows |
| 4 | Autenticación + multi-tenant | Alta | Alta | BD | 80 | Permite vender a más de 1 cliente |
| 5 | Alertas por umbral (email) | Alta | Baja | Agentes, BD | 30 | Engagement diario del cliente |
| 6 | Reporte ejecutivo PDF | Alta | Alta | Agentes, LM Studio | 80 | Valor percibido alto para directivos |
| 7 | LM Studio - análisis básico | Alta | Media | Servidor con GPU/RAM | 50 | Diferenciación vs competidores |
| 8 | Agente VMware | Alta | Alta | Agente Linux | 80 | Empresas con virtualización |
| 9 | Active Directory users | Alta | Media | Agente Windows | 40 | Seguridad - gran preocupación |
| 10 | Backup Veeam | Alta | Media | Agente Windows | 40 | Recuperación - venta cruzada |
| 11 | Predicción disco (ARIMA) | Alta | Alta | 30+ días de datos | 60 | "Prevenir antes que curar" |
| 12 | Portal de clientes (config) | Media | Alta | Autenticación | 60 | Reducción de soporte |
| 13 | Agente de red (SNMP) | Media | Alta | Nmap, SNMP | 80 | Valor agregado |
| 14 | Predicción logs (XGBoost) | Media | Alta | 90+ días de datos | 80 | Diferenciación técnica |
| 15 | Anomaly detection con IA | Media | Alta | LM Studio avanzado | 60 | Característica estrella |
| 16 | Reportes técnicos detallados | Media | Alta | Reportes ejecutivos | 80 | Para administradores IT |
| 17 | Office365 / Exchange | Media | Media | Agente Windows | 40 | Cloud - tendencia creciente |
| 18 | API pública + webhooks | Media | Alta | Multi-tenant | 60 | Ecosistema e integraciones |
| 19 | MFA + RBAC completo | Media | Alta | Autenticación | 40 | Compliance - ventas Enterprise |
| 20 | On-premise deployment | Baja | Muy alta | Todo lo anterior | 120 | Clientes regulados |
| 21 | App mobile | Baja | Muy alta | API pública | 120 | Conveniencia - retención |
| 22 | Marketplace integraciones | Baja | Muy alta | API, webhooks | 160 | Crecimiento exponencial |
| 23 | White-label para MSPs | Baja | Muy alta | Multi-tenant | 200 | Canal de ventas |
| 24 | ISO 27001 certification | Baja | Muy alta | Seguridad completa | 300 | Enterprise deals |
| 25 | SOC 2 Type II | Baja | Muy alta | ISO 27001 | 500 | Compliance USA |

**Total horas estimadas para MVP:** ~300 horas (2 meses trabajando full-time)  
**Total horas estimadas año 1:** ~2,200 horas  
**Costo total desarrollo estimado:** ~$45,000-$65,000 USD (dependiendo de tasa del desarrollador)

---

## Notas del CTO

### Riesgos Clave Identificados
1. **LM Studio en GPU**: Si no se consigue GPU, la inferencia en CPU es 3-5 tok/s - suficiente para batch analysis pero no para tiempo real
2. **Adopción PyME**: El onboarding técnico es la barrera. Invertir en wizard de instalación
3. **Pricing Argentina**: Dólar oficial vs blue, inflación. Revisar precios trimestralmente
4. **Competencia**: Zabbix/Prometheus son gratis pero complejos. PRTG/Datadog son caros. InfraDoctor compite en "suficientemente bueno + IA + precio justo"

### Estrategia de Salida
- **Año 1-2**: Growth con PyMEs locales (Argentina + Latam)
- **Año 3**: Expansión a USA con canales MSP
- **Año 4-5**: Adquisición por empresa de observabilidad (Datadog/New Relic/Dynatrace) o Private Equity

### Métricas Clave de Éxito (OKRs)
- **Q1**: 5 clientes pagos, NPS > 40
- **Q2**: 25 clientes, ARR $50k, Churn < 5%
- **Q3**: 50 clientes, ARR $120k
- **Q4**: 100+ clientes, ARR $250k+, 2 contratos Enterprise
