# AGENTS.md

Parking-lot management desktop app ("Ciudad de Burgos"), Spanish UI.

## Stack & running
- Python 3.12, virtualenv at `.venv`. GUI dep is `customtkinter` (already installed).
- Layered architecture (no framework, no ORM):
  - `domain/` — entities, enums, pure business rules (`reglas.py`): billing, vencimientos, ocupación. No I/O.
  - `infrastructure/` — SQLite access (`db.py` connection factory + `repos.py` repositories), file outputs (`archivos.py` tickets/cierres). Single `DB_PATH` via `pathlib` (no hardcoded absolute paths).
  - `services/` — use cases (`casos_uso.py`) orchestrating repos + rules; raises typed `ValidacionError`/`ConfiguracionFaltante`.
  - `ui/` — `gui_dashboard.py` (customtkinter). Thin: only calls services, no SQL.
  - `app/bootstrap.py` — `main()`: `db.inicializar()` then launches the dashboard.
- Entrypoint: `main.py`. Run: `.venv/bin/python main.py` (needs a display / X server for the Tk GUI).
- Install deps/dev: `.venv/bin/pip install -e ".[dev]"`; tests: `.venv/bin/python -m pytest`.

## Data & storage
- SQLite DB at `parqueadero.db`, created/seeded automatically on startup by `db.inicializar()`.
- **`parqueadero.db` is git-ignored** (contains customer PII: plates, names, phones). It is NOT committed. Same for `tickets/` and `reportes_cierre/`.
- `configuracion` table is keyed by `tipo_vehiculo` (Moto Hora, Moto Mes, Carro, Carro Mes, Camion, Autobus, Otros Mes) with columns `tarifa_hora`, `tarifa_mes`, `cupos_totales`. Seeded with defaults; monthly pricing uses `tarifa_mes" not `tarifa_hora`.
- No migrations framework: schema lives in `db.crear_tablas()` (idempotent; adds `tarifa_mes` via `ALTER` if missing).

## Conventions / gotchas (verified)
- Never put SQL or `conectar()` outside `infrastructure/`. The GUI must call `services.casos_uso`, not touch the DB directly.
- Business rules are pure functions in `domain/reglas.py` and covered by `tests/`. Add new rules there, not in the UI.
- `estado` values are the `EstadoIngreso` enum (`EN SITIO`, `FINALIZADO`); monthly payments are stored in `ingresos` with `tipo` `PAGO MES` / `RENOVACIÓN MES` (not a config key) — cierre report classifies by these.
- Tests use a temp DB via `PARQUEADERO_DB` env var (set in `tests/conftest.py`); they never touch the real `parqueadero.db`.
- No `requirements.txt`; deps declared in `pyproject.toml`.
