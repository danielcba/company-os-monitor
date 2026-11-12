# Guía de Usuario — Módulo de Conexión a SAP R/3

**Plataforma:** Company-OS-Monitor
**Módulo:** Integración SAP R/3 (capacidad externa no-canónica)
**Versión de la guía:** 1.0 (2026-11-12)

---

## 1. ¿Qué hace este módulo?

El módulo de integración permite que **Company-OS-Monitor** envíe información a
**SAP R/3** (el sistema ERP de la empresa). En concreto, envía el **costo de
las caídas (downtime)** de los servidores/servicios monitoreados.

Imaginá esta situación:

1. La plataforma monitorea un servidor y detecta que estuvo caído durante 2 horas.
2. Ese servidor tiene una "tarifa" horaria (por ejemplo, 100 USD/hora).
3. El módulo calcula el costo: 2 horas × 100 USD = 200 USD.
4. El módulo envía esa cifra a SAP, como un registro contable de la caída.

> **Concepto clave:** el módulo **no decide** qué es una caída ni **no
> inventa** tarifas. Solo toma decisiones que la plataforma ya tomó (de forma
> segura y calibrada) y las convierte en información que SAP puede procesar.

---

## 2. ¿Para qué sirve? (valor de negocio)

- **Contabilidad de caídas:** registrar automáticamente el costo de cada caída
  de infraestructura en SAP.
- **Información financiera directa:** los equipos de finanzas ven en SAP cuánto
  cuesta cada incidente, sin cruzar datos manualmente.
- **Trazabilidad:** cada envío queda registrado (qué se mandó, cuándo, con qué
  resultado), para auditoría.

---

## 3. Cómo se compone (las 3 partes)

El módulo tiene 3 piezas que trabajan juntas:

| Pieza | Qué hace | Analogía |
|---|---|---|
| **1. Datos financieros** (Fase 1) | Guarda la tarifa horaria y la moneda de cada servidor/servicio | El "precio por hora" de cada activo |
| **2. Conector SAP** (Fase 2) | Habla con SAP (envía la información y confirma que llegó) | El "cartero" que entrega el sobre |
| **3. Puente** (Fase 3) | Une la decisión de la plataforma con el envío a SAP | El "coordinador" que arma el sobre y le pide al cartero que lo entregue |

---

## 4. ¿Qué información se envía a SAP?

El módulo envía dos tipos de datos:

### a) Costo de caída (el principal)
- **Cuánto tiempo** estuvo caído el activo (en horas).
- **Tarifa horaria** del activo (de los datos financieros).
- **Moneda** (por ejemplo, USD, ARS, EUR).
- **Referencia**: identificador del activo y de la decisión que originó el envío.

**Cálculo:** `costo = horas × tarifa horaria`

### b) Métricas ponderadas (disponible para uso futuro)
- Métricas con un peso por activo/servicio (ej. disponibilidad).

---

## 5. Lo que el módulo NO hace (importante)

Para evitar malentendidos, esto es lo que el módulo **explícitamente no hace**:

- ❌ **No decide** si un servidor está caído (eso lo hace el "cerebro" cognitivo de la plataforma).
- ❌ **No inventa** tarifas ni monedas (si no están cargadas, no envía nada).
- ❌ **No toma decisiones** por sí mismo: solo ejecuta envíos que ya fueron autorizados.
- ❌ **No modifica** los datos internos de la plataforma (solo lee y envía hacia SAP).

> Esto es una decisión de diseño deliberada: mantiene la seguridad y la
> confiabilidad del sistema completo.

---

## 6. Requisitos para que funcione

Para que el módulo pueda enviar información a SAP, se necesitan 3 cosas:

| # | Requisito | Dónde se configura |
|---|---|---|
| 1 | **Tarifa horaria y moneda** de cada activo | En los datos financieros del activo |
| 2 | **Usuario de SAP** autorizado para registrar envíos | En la configuración del conector (secretos) |
| 3 | **Destino de SAP** (sistema RFC) accesible | En la configuración del conector |
| 4 | Una **decisión** de la plataforma que origine el envío | La genera el flujo cognitivo de la plataforma |

> **Importante:** si falta la tarifa del activo o el usuario de SAP, el módulo
> **no envía nada** (se niega de forma segura). Esto evita errores y datos incompletos.

---

## 7. Cómo se comporta ante errores (seguridad)

- **Si SAP no responde a tiempo:** el módulo cancela el intento y lo registra como fallido. No se queda colgado esperando.
- **Si el envío falla:** se revierte cualquier cambio parcial en SAP (rollback) y se registra el error.
- **Si se intenta enviar dos veces lo mismo:** el módulo lo detecta y **no duplica** el envío (evita cargar dos veces el mismo costo).
- **Nunca bloquea la plataforma:** si SAP está caído o mal configurado, el resto de la plataforma sigue funcionando normal.

---

## 8. ¿Cómo se usa en la práctica?

El módulo funciona de forma **automática**. No hay que "operarlo" a mano:

1. La plataforma detecta una caída y toma una **decisión** (con confianza calibrada).
2. El módulo detecta esa decisión, busca la tarifa del activo y arma el envío.
3. El módulo envía a SAP y registra el resultado (éxito / fallo).

**Para el personal de operaciones/finanzas:** solo necesitan ver en SAP los
registros que llegan. Si algo falla, el módulo lo deja registrado y no se pierde
la información (queda en el log, sin borrarse).

---

## 9. Seguridad y confianza

- **Autenticación:** el usuario de SAP se configura como secreto; nunca aparece en el código.
- **Registro inmutable:** cada envío se guarda en un registro que no se puede modificar ni borrar (para auditoría).
- **Separación de tenants:** cada cliente (tenant) solo ve y envía sus propios datos.
- **Validación estricta:** no se aceptan valores negativos ni monedas inválidas.

---

## 10. Resumen rápido (TL;DR)

| Pregunta | Respuesta |
|---|---|
| ¿Qué hace? | Envía el costo de caídas de servidores a SAP R/3 |
| ¿Cómo calcula el costo? | Horas caídas × tarifa horaria del activo |
| ¿Dónde están las tarifas? | En los datos financieros de cada activo |
| ¿Qué necesita para funcionar? | Tarifa del activo + usuario SAP + destino SAP accesible |
| ¿Qué pasa si falta algo? | No envía nada (se niega de forma segura) |
| ¿Puede duplicar envíos? | No, lo evita automáticamente |
| ¿Afecta al resto de la plataforma si SAP falla? | No, la plataforma sigue funcionando |
| ¿Deja rastro? | Sí, un registro de auditoría que no se puede borrar |

---

## 11. Glosario

- **SAP R/3:** sistema de planificación de recursos empresariales (ERP) usado para gestionar finanzas, logística, etc.
- **Downtime:** tiempo durante el cual un servicio o servidor está caído.
- **Tarifa horaria:** costo por hora de un activo (usado para calcular el costo de la caída).
- **Tenant:** cliente/espacio aislado dentro de la plataforma.
- **RFC/BAPI:** el estándar técnico que SAP usa para recibir información desde sistemas externos.
- **Rollback:** revertir un cambio a medias cuando algo falla.
- **Idempotencia:** garantía de que repetir una operación no produce un efecto duplicado.
