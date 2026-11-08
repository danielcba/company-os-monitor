# Resumen Ejecutivo — Opciones de Licenciamiento

**Propósito:** ayudar al dueño (Daniel) a tomar la **decisión de licencia**
del repositorio `company-os-monitor`. Está **BLOCKED** en el flujo de release
(`release-policy.md`: "LICENSE STATUS = OWNER DECISION REQUIRED"; journal D45).
Este documento presenta las opciones con sus pros/contras para decidir con
criterio legal y técnico.

---

## 1. Estado actual

- **No existe archivo `LICENSE`** en el repositorio.
- La política de release exige una decisión del dueño antes de un release formal.
- El código es **código original del dueño** (no derivado de otros proyectos de
  código abierto sin licencia propia). Esto da libertad total de elección.

---

## 2. Factores a considerar (según el objetivo)

El proyecto tiene dos objetivos que compiten:
1. **Código abierto / comunidad** — atraer colaboradores, mostrar el trabajo.
2. **Protección comercial / control** — si se planea comercializar o mantener
   control exclusivo.

La licencia define qué pueden hacer otros con el código. No hay opción
"neutral": la ausencia de licencia implica **todos los derechos reservados**
(no se permite uso/redistribución).

---

## 3. Opciones de licenciamiento

### Opción A — MIT (permisiva)

**Qué permite:** uso, copia, modificación, distribución, uso comercial y
sublicencia, con atribución (conservar el aviso de copyright). Sin garantías.

**Pros**
- Máxima adopción: es la más usada y entendida (React, jQuery, .NET Core).
- Fácil de integrar en proyectos de empresas (bajo riesgo legal).
- Atrae colaboradores y contribuciones.
- Una sola página, sin obligaciones complejas.

**Contras**
- Cualquiera puede usar el código comercialmente **sin compartir sus cambios**
  (fork cerrado permitido).
- No protege la diferenciación si se quiere comercializar como producto
  "cerrado".

**Ideal si:** el objetivo es visibilidad, adopción y comunidad.

---

### Opción B — Apache-2.0 (permisiva + patentes)

**Qué permite:** igual que MIT, pero **con concesión explícita de patentes** y
protección de contribuidores. Es la licencia "amigable para empresas".

**Pros**
- Seguridad legal adicional (terminación de licencia de patentes si se demanda).
- Compatible con el ecosistema corporativo (Google, Apache, etc.).
- Bien redactada y estándar de facto para infraestructura.

**Contras**
- Misma "debilidad" que MIT: permite forks cerrados/comerciales sin compartir.
- Algo más larga y compleja (aunque sigue siendo manejable).

**Ideal si:** se busca máxima adopción con protección de patentes y apariencia
corporativa.

---

### Opción C — GPL-3.0 (copyleft fuerte)

**Qué permite:** uso, modificación y distribución, pero **obliga a que las
obras derivadas también sean GPL** (compartir el código de los cambios).

**Pros**
- Garantiza que el código y sus derivados sigan siendo abiertos.
- Muy respetada en la comunidad de software libre (Linux, Git).
- Impide forks cerrados.

**Contras**
- **Incompatible con uso comercial propietario**: una empresa no puede
  integrarlo en un producto cerrado sin liberar su propio código.
- Puede desalentar adopción corporativa.
- Obligaciones más complejas (licenciar derivados, cumplir copyleft).

**Ideal si:** se quiere garantizar que nadie "cierre" el proyecto.

---

### Opción D — AGPL-3.0 (copyleft fuerte + red)

**Qué permite:** igual que GPL, pero además cubre el uso **vía red** (SaaS):
si el software se ofrece como servicio web, debe liberarse el código del
servicio.

**Pros**
- Protege el código incluso para uso SaaS (muy relevante para una plataforma
  de monitoreo como servicio).
- Impide que alguien la explote como servicio cerrado sin compartir.

**Contras**
- La más restrictiva para uso comercial/reuso.
- Desalienta aún más la adopción empresarial.
- Obligaciones legales pesadas.

**Ideal si:** la plataforma se va a ofrecer como **servicio (SaaS)** y se
quiere evitar que otros la repliquen como servicio cerrado.

---

### Opción E — Licencia propietaria (todos los derechos reservados)

**Qué permite:** nada por defecto; el dueño otorga permisos caso por caso.

**Pros**
- Máximo control y protección comercial.
- Permite vender licencias o cerrar el código.
- No hay obligaciones de compartir.

**Contras**
- Cero adopción externa / cero comunidad.
- No sirve como vitrina de habilidades (clave para tu re-inserción laboral).
- Requiere un EULA y gestión legal activa.

**Ideal si:** se va a comercializar como producto cerrado y no interesa la
comunidad.

---

### Opción F — Dual license (propietaria + código abierto)

**Qué permite:** ofrecer el mismo código bajo dos licencias: una abierta (ej.
AGPL) para la comunidad, y una comercial (pagada) para empresas que no quieran
cumplir el copyleft.

**Pros**
- Equilibrio: comunidad + ingresos.
- Muy usado por proyectos SaaS exitosos.

**Contras**
- Complejidad legal y de gestión alta.
- Requiere definir claramente la línea entre ambas ediciones.

**Ideal si:** se planea comercializar manteniendo una versión abierta.

---

## 4. Recomendación (alineada al roadmap y tu objetivo)

El roadmap del proyecto ya contempla **certificación ISO 27001** y el proyecto
es tu **vehículo de re-inserción laboral** (vitrina). Por eso:

- **Si el objetivo primario es visibilidad + comunidad** (mi recomendación):
  **Apache-2.0** (equilibrio entre adopción y protección de patentes) o
  **MIT** (máxima simpleza).
- **Si se va a ofrecer como SaaS** y se quiere evitar replicas cerradas:
  **AGPL-3.0**.
- **Si el objetivo es comercializar como producto cerrado**: **propietaria**.

**Recomendación concreta:** **Apache-2.0** si se prioriza la comunidad con un
perfil "producto de infraestructura de nivel empresarial" (coherente con ISO
27001). Alternativamente **MIT** si se prioriza la simpleza absoluta.

---

## 5. Próximo paso

1. Elegir el **identificador SPDX** exacto (case-sensitive, según la allowlist
   del proyecto): `MIT`, `Apache-2.0`, `GPL-3.0-only`, `AGPL-3.0-only`, etc.
2. Proceder a **crear el `LICENSE`** (el flujo D45 lo desbloqueará).
3. Esto desbloqueará la preparación del próximo release (v0.1.2).
