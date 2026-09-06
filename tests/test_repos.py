from datetime import datetime

import pytest

from infrastructure import repos
from domain.enums import EstadoReporte


def test_registrar_y_buscar_en_sitio():
    repo = repos.IngresoRepo()
    ing = repo.registrar_entrada("abc123", "Carro", "Yamaha", "Ana", "123")
    assert ing.id is not None
    assert ing.estado.value == "EN SITIO"

    encontrado = repo.buscar_en_sitio("abc123")
    assert encontrado is not None
    assert encontrado.placa == "ABC123"


def test_repositorio_rechaza_duplicado_activo():
    repo = repos.IngresoRepo()
    repo.registrar_entrada("dup1", "Carro", "", "", "")

    with pytest.raises(repos.IngresoActivoDuplicadoPersistenceError):
        repo.registrar_entrada("DUP1", "Carro", "", "", "")

    assert len(repo.listar_en_sitio()) == 1


def test_repositorio_permite_duplicados_finalizados():
    repo = repos.IngresoRepo()
    primero = repo.registrar_entrada("hist1", "Carro", "", "", "")
    repo.finalizar(primero.id, datetime(2026, 1, 1, 12, 0), 1000.0)
    segundo = repo.registrar_entrada("HIST1", "Carro", "", "", "")
    repo.finalizar(segundo.id, datetime(2026, 1, 1, 13, 0), 2000.0)

    assert len(repo.listar_en_sitio()) == 0


def test_indice_unico_de_ingresos_activos_existe():
    from infrastructure import db

    with db.get_connection() as conn:
        indices = {row[1] for row in conn.execute("PRAGMA index_list(ingresos)")}

    assert "ux_ingresos_placa_en_sitio" in indices


def test_registrar_cierre_rechaza_fecha_repetida():
    repo = repos.CierreRepo()
    repo.registrar("2026-09-01", 100.0, 1)

    with pytest.raises(repos.CierreDiarioDuplicadoPersistenceError):
        repo.registrar("2026-09-01", 200.0, 2)

    assert repo.existe_por_fecha("2026-09-01")


def test_registrar_cierres_de_fechas_diferentes():
    repo = repos.CierreRepo()

    repo.registrar("2026-09-01", 100.0, 1)
    repo.registrar("2026-09-02", 200.0, 2)

    assert repo.existe_por_fecha("2026-09-01")
    assert repo.existe_por_fecha("2026-09-02")


def test_cierre_persiste_y_recupera_snapshot():
    repo = repos.CierreRepo()
    inventario = [("ABC123", "Carro", "2026-09-01 08:00:00")]

    creado = repo.registrar(
        "2026-09-01",
        175000.0,
        2,
        total_horas=100000.0,
        cantidad_horas=1,
        total_mensualidades=75000.0,
        cantidad_mensualidades=1,
        inventario_snapshot=inventario,
        estado_reporte=EstadoReporte.PENDIENTE,
    )
    recuperado = repo.obtener_por_id(creado.id)

    assert recuperado.total_horas == 100000.0
    assert recuperado.cantidad_horas == 1
    assert recuperado.total_mensualidades == 75000.0
    assert recuperado.cantidad_mensualidades == 1
    assert recuperado.total == 175000.0
    assert recuperado.vehiculos_salida == 2
    assert recuperado.inventario_snapshot == inventario
    assert recuperado.estado_reporte == EstadoReporte.PENDIENTE


def test_cierre_persiste_estados_generado_y_error():
    repo = repos.CierreRepo()

    generado = repo.registrar("2026-09-02", 100.0, 1, estado_reporte=EstadoReporte.GENERADO)
    error = repo.registrar("2026-09-03", 100.0, 1, estado_reporte=EstadoReporte.ERROR)

    assert repo.obtener_por_id(generado.id).estado_reporte == EstadoReporte.GENERADO
    assert repo.obtener_por_id(error.id).estado_reporte == EstadoReporte.ERROR


def test_actualizar_estado_reporte_condicional_no_degrada_generado():
    repo = repos.CierreRepo()
    cierre = repo.registrar("2026-09-05", 100.0, 1, estado_reporte=EstadoReporte.ERROR)

    assert repo.actualizar_estado_reporte_condicional(
        cierre.id,
        EstadoReporte.GENERADO,
    )
    assert not repo.actualizar_estado_reporte_condicional(
        cierre.id,
        EstadoReporte.ERROR,
    )
    assert repo.obtener_por_id(cierre.id).estado_reporte == EstadoReporte.GENERADO


def test_actualizar_estado_reporte_condicional_rechaza_pendiente():
    repo = repos.CierreRepo()
    cierre = repo.registrar("2026-09-04", 100.0, 1, estado_reporte=EstadoReporte.ERROR)

    with pytest.raises(ValueError):
        repo.actualizar_estado_reporte_condicional(
            cierre.id, EstadoReporte.PENDIENTE
        )


def test_cierre_compatible_sin_snapshot():
    repo = repos.CierreRepo()
    creado = repo.registrar("2026-09-01", 0.0, 0)

    recuperado = repo.obtener_por_id(creado.id)

    assert recuperado.inventario_snapshot is None


def test_migracion_agrega_estado_a_esquema_historico(tmp_path, monkeypatch):
    import sqlite3
    from infrastructure import db

    ruta = tmp_path / "historica.db"
    conn = sqlite3.connect(ruta)
    conn.execute(
        """CREATE TABLE cierres_caja (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               fecha TEXT, total REAL, vehiculos_salida INTEGER)"""
    )
    conn.execute(
        "INSERT INTO cierres_caja (fecha, total, vehiculos_salida) VALUES (?, ?, ?)",
        ("2026-09-01", 100.0, 1),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", ruta)

    db.crear_tablas()
    db.crear_tablas()

    with db.get_connection() as conn:
        columnas = [row[1] for row in conn.execute("PRAGMA table_info(cierres_caja)")]
        estado = conn.execute("SELECT estado_reporte FROM cierres_caja").fetchone()[0]

    assert columnas.count("estado_reporte") == 1
    assert estado is None


def test_migracion_de_cierres_es_idempotente():
    from infrastructure import db

    db.crear_tablas()
    db.crear_tablas()

    with db.get_connection() as conn:
        indices = {row[1] for row in conn.execute("PRAGMA index_list(cierres_caja)")}

    assert "ux_cierres_caja_fecha" in indices


def test_error_de_integridad_no_relacionado_no_es_duplicado(monkeypatch):
    class FailingConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def execute(self, *args):
            raise sqlite3.IntegrityError("other constraint")

    import sqlite3

    monkeypatch.setattr(repos.db, "get_connection", lambda: FailingConnection())

    with pytest.raises(sqlite3.IntegrityError):
        repos.CierreRepo().registrar("2026-09-01", 100.0, 1)


def test_finalizar_marca_salida():
    repo = repos.IngresoRepo()
    ing = repo.registrar_entrada("xyz", "Moto Hora", "Honda", "", "")
    salida = datetime(2026, 1, 1, 12, 0)
    repo.finalizar(ing.id, salida, 5000.0)

    assert repo.buscar_en_sitio("xyz") is None
    por_id = repo.obtener_por_id(ing.id)
    assert por_id.estado.value == "FINALIZADO"
    assert por_id.valor_pagado == 5000.0


def test_contar_y_listar_en_sitio():
    repo = repos.IngresoRepo()
    repo.registrar_entrada("a", "Carro", "", "", "")
    repo.registrar_entrada("b", "Carro", "", "", "")
    repo.registrar_entrada("c", "Moto Hora", "", "", "")

    conteo = repo.contar_en_sitio_por_tipo()
    assert conteo["Carro"] == 2
    assert conteo["Moto Hora"] == 1
    assert len(repo.listar_en_sitio()) == 3


def test_mensualidad_repo_crud():
    repo = repos.MensualidadRepo()
    pago = datetime(2026, 1, 1)
    venc = datetime(2026, 1, 31)
    repo.registrar("mes1", "Toyota", "Luis", "999", "Moto Mes", pago, venc)
    assert repo.obtener_por_placa("mes1") is not None

    repo.renovar("mes1", pago, datetime(2026, 3, 2))
    assert repo.obtener_por_placa("mes1").fecha_vencimiento == datetime(2026, 3, 2)

    repo.eliminar("mes1")
    assert repo.obtener_por_placa("mes1") is None


def test_configuracion_seed_tiene_tarifa_mes():
    repo = repos.ConfiguracionRepo()
    cfg = repo.obtener("Moto Mes")
    assert cfg is not None
    assert cfg.tarifa_mes > 0


def test_resumen_dia_separa_horas_y_meses():
    ing = repos.IngresoRepo()
    ing.registrar_entrada("h1", "Carro", "", "", "")
    ing.finalizar(ing.buscar_en_sitio("h1").id, datetime(2026, 1, 1, 12), 165000.0)
    ing.registrar_pago_mes("m1", "Moto", "Pepe", "PAGO MES", datetime(2026, 1, 1, 10, 0), 75000.0)

    resumen = ing.resumen_dia("2026-01-01")
    assert resumen["horas_total"] == 165000.0
    assert resumen["mes_total"] == 75000.0
    assert resumen["mes_count"] == 1
