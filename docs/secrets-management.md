# Secrets Management — Company OS Monitor

**Estado:** Activo (mejora de seguridad 1b)
**Aplica a:** `company-os-monitor` (el producto) y su despliegue.

---

## 1. Introducción

Este documento define cómo gestionar los secretos de la plataforma de forma
segura. El objetivo es que ningún secreto quede en texto plano en el
repositorio, ni se arranque con valores de plantilla (`placeholder`), y que la
transición a producción sea robusta.

---

## 2. Principios

- **Nunca commitear secretos.** El `.env` (real) está en `.gitignore`; solo se
  commitea `.env.example` con valores de plantilla.
- **Fail-closed.** La plataforma no arranca si un secreto es un placeholder
  (público/predecible). Se valida antes de crear contenedores (ver `start.sh`).
- **Mínimo privilegio.** Cada servicio usa solo los secretos que necesita.
- **Rotación.** Los secretos deben poder regenerarse sin recompilar.
- **Separación dev/prod.** Los valores de desarrollo difieren de los de
  producción; nunca reutilizar secretos reales en repositorios.

---

## 3. Secretos de la plataforma

| Secreto | Para qué | Dónde se usa |
|---|---|---|
| `POSTGRES_PASSWORD` | Auth de PostgreSQL | `docker-compose.yml`, `DATABASE_URL` |
| `REDIS_PASSWORD` | Auth de Redis (requirepass) | `docker-compose.yml`, URLs Redis |
| `DATABASE_URL` | Conexión a PostgreSQL (contiene la password) | Servicios del pipeline, gateway |
| `JWT_SECRET_KEY` | Firma HS256 (dev) | user-service / gateway |
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | Firma/verificación RS256 (prod) | user-service / gateway |
| `WINRM_PASSWORD` / `VCENTER_PASSWORD` | Agentes Windows/VMware | agentes |

---

## 4. Generación de secretos (desarrollo)

```bash
# Secretos aleatorios seguros (hex 128-bit / 256-bit)
openssl rand -hex 16   # contraseñas (PG, Redis)
openssl rand -hex 32   # JWT_SECRET_KEY

# Par de claves RS256 para producción (JWT)
openssl genrsa -out jwt_private.pem 2048
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
# -> copiar contenido a JWT_PRIVATE_KEY / JWT_PUBLIC_KEY en .env (no commitear)
```

**Uso:** copiar `.env.example` a `.env` (no commitear), generar valores reales y
completar.

---

## 5. Rotación de secretos

- **JWT HS256** (dev): regenerar `JWT_SECRET_KEY` invalida todos los tokens
  emitidos; coordinar el reinicio de user-service + gateway.
- **JWT RS256** (prod): se recomienda rotar por `kid` (ver `MachineJwtService`).
  Agregar la clave nueva al `key_set`, dejarla en la ventana de overlap, y luego
  retirar la vieja.
- **PostgreSQL/Redis**: rotar la password en el contenedor y actualizar
  `DATABASE_URL`/`REDIS_URL`; reiniciar los servicios.

---

## 6. Recomendación para producción (gestión centralizada)

Para producción, se recomienda **no** confiar solo en `.env` en el servidor:

1. **Vault (HashiCorp)** o **Kubernetes Secrets**: inyectar los secretos como
   variables de entorno en el runtime, nunca en el repo.
2. **Secretos por entorno**: un `.env.prod` fuera del repo (o el mecanismo de
   secretos del orquestador), con valores reales.
3. **No dejar `.env` con secretos en el filesystem del contenedor**; usar
   montajes de secretos o variables de entorno inyectadas.
4. **Auditar**: revisar que ningún secreto esté en logs o en el historial git
   (ver `.github/workflows/secret_scanning.yml`).

---

## 7. Verificación

- `grep -r "REPLACE-WITH\|CHANGE-ME" --include=.env` no debe devolver nada.
- El fail-closed de `start.sh` aborta si hay placeholders de JWT/PG/Redis.
- `git status` no debe mostrar `.env` (está en `.gitignore`).
