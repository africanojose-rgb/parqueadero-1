# Ciudad de Burgos — Sistema de Parqueadero

Aplicación de escritorio (Python + customtkinter) para gestión de un parqueadero:
entradas/salidas por hora, mensualidades, reportes y cierres de caja.

## Arquitectura

Código organizado por capas (sin frameworks pesados):

- `domain/` — entidades, enumerados y reglas de negocio puras (testeables, sin I/O).
- `infrastructure/` — acceso a datos SQLite (repositorios), rutas y generación de tickets/cierres.
- `services/` — casos de uso que orquestan repositorios y reglas de negocio.
- `ui/` — capa de presentación (customtkinter); solo invoca servicios.
- `app/` — punto de composición (`bootstrap.main`).

## Puesta en marcha

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"   # instala customtkinter + pytest
.venv/bin/python main.py            # inicia el dashboard (requiere entorno gráfico)
```

La base de datos `parqueadero.db` se crea y seeds automáticamente al arrancar.
**No se versiona** (contiene datos personales de clientes); ver `.gitignore`.

## Pruebas

```bash
.venv/bin/python -m pytest
```

## Configuración

Los precios/cupos por tipo de vehículo se guardan en la tabla `configuracion`
y se editan desde la pestaña ⚙️ CONFIGURACIÓN de la interfaz.
