# AGROWAVE API

Backend de AGROWAVE: monolito modular en Python 3.12 + FastAPI con arquitectura limpia.

## Requisitos
- Docker Desktop (Compose v2).
- Repositorio `agro-wave-front` clonado como carpeta hermana (`../agro-wave-front`): el
  servicio `web` de `compose.yaml` lo monta.

## Arranque en desarrollo
```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

| Servicio | URL en el host |
|---|---|
| web (Vite) | http://localhost:5173 |
| api (FastAPI) | http://localhost:8000/api/v1/health |
| OpenAPI | http://localhost:8000/api/v1/docs |
| minio (consola) | http://localhost:9001 |
| db (PostgreSQL) | localhost:`DB_HOST_PORT` (5433 por defecto, para no chocar con un PostgreSQL local) |

Al arrancar, `api` aplica las migraciones (`alembic upgrade head`) y crea el bucket de DEM si
no existe (`python -m agrowave.bootstrap`). Ambas acciones son idempotentes.

## Verificación
Todo se ejecuta dentro del contenedor `api`, contra los servicios `db` y `minio`:
```powershell
docker compose run --rm api ruff check .
docker compose run --rm api ruff format --check .
docker compose run --rm api mypy
docker compose run --rm api lint-imports
docker compose run --rm api pytest
```
Las pruebas de integración usan la base `agrowave_test` y el bucket `agrowave-dems-test`; los
fixtures los crean y los vacían.

## Migraciones
```powershell
docker compose run --rm api alembic upgrade head
docker compose run --rm api alembic revision --autogenerate -m "<module>: <change>"
docker compose run --rm api alembic check
```
Toda migración autogenerada se revisa a mano.

## Volúmenes
| Volumen | Contenido |
|---|---|
| db-data | PostgreSQL de desarrollo |
| minio-data | Bucket `agrowave-dems` |
| fabdem-cache | Teselas FABDEM descargadas (caché recuperable) |

`docker compose down` conserva los volúmenes.

> **Acción destructiva:** `docker compose down -v` borra los volúmenes (base de datos, DEM y
> caché). Úsalo solo si quieres empezar de cero.
