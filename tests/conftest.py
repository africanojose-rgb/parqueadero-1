import os
import tempfile

# Fijar la ruta de la BD antes de importar cualquier módulo del proyecto.
_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["PARQUEADERO_DB"] = _DB_PATH

import pytest


@pytest.fixture(autouse=True, scope="session")
def _init_db():
    from infrastructure import db

    db.crear_tablas()
    db.sembrar_configuracion()
    yield
    if os.path.exists(_DB_PATH):
        os.unlink(_DB_PATH)


@pytest.fixture(autouse=True)
def _limpiar_datos():
    from infrastructure import db

    with db.get_connection() as c:
        c.executescript(
            "DELETE FROM ingresos; DELETE FROM mensualidades; DELETE FROM cierres_caja;"
        )
    yield


@pytest.fixture(autouse=True)
def _aislar_tickets(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "TICKETS_DIR", tmp_path / "tickets")
