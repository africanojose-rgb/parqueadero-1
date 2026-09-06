from datetime import datetime

import pytest

import services.casos_uso as svc
from services.exceptions import (
    CierreDiarioYaExiste,
    CierreNoEncontrado,
    CierreSinSnapshot,
    ConfiguracionFaltante,
    IngresoActivoDuplicado,
    ValidacionError,
)
from domain.enums import EstadoReporte


def test_registrar_entrada_valida_placa():
    with pytest.raises(ValidacionError):
        svc.registrar_entrada("", "Carro", "", "", "")


def test_flujo_entrada_salida():
    svc.registrar_entrada("car1", "Carro", "Corolla", "Ana", "123")
    cobro = svc.previsualizar_cobro("car1")
    assert cobro["horas"] >= 1
    assert cobro["total"] == cobro["horas"] * cobro["tarifa"]

    res = svc.cobrar_salida("car1")
    assert "ticket" in res
    assert svc.buscar_placa("car1") is None


def test_registrar_entrada_duplicada_lanza_error_y_conserva_una_activa():
    svc.registrar_entrada(" dup1 ", "Carro", "", "", "")

    with pytest.raises(IngresoActivoDuplicado):
        svc.registrar_entrada("DUP1", "Carro", "", "", "")

    assert svc.buscar_placa("dup1") is not None
    assert len(svc.listar_en_sitio()) == 1


def test_placa_puede_reingresar_despues_de_finalizar():
    svc.registrar_entrada(" re1 ", "Carro", "", "", "")
    svc.cobrar_salida("RE1")

    svc.registrar_entrada(" re1 ", "Carro", "", "", "")

    assert len(svc.listar_en_sitio()) == 1


def test_cobrar_sin_en_sitio_falla():
    with pytest.raises(ValidacionError):
        svc.cobrar_salida("noexiste")


def test_mensualidad_precio_real():
    res = svc.registrar_mensualidad("m1", "Honda", "Luis", "999", "Moto Mes")
    assert res["precio"] == 75000.0
    mens = svc.listar_mensualidades()
    assert any(m["placa"] == "M1" for m in mens)


def test_mensualidad_tipo_invalido():
    with pytest.raises(ValidacionError):
        svc.registrar_mensualidad("m2", "", "", "", "Carro")


def test_renovar_mensualidad():
    svc.registrar_mensualidad("m3", "Honda", "Luis", "999", "Moto Mes")
    res = svc.renovar_mensualidad("m3")
    assert res["precio"] == 75000.0


def test_ocupacion_cuenta_mensuales():
    svc.registrar_mensualidad("mm", "Honda", "Luis", "999", "Moto Mes")
    svc.registrar_entrada("hh", "Moto Hora", "", "", "")
    ocu = svc.calcular_ocupacion()
    assert ocu["moto_mes"][0] == 1
    assert ocu["moto_hora"][0] == 1


def test_guardar_configuracion_valida_numericos():
    with pytest.raises(ValidacionError):
        svc.guardar_configuracion("Carro", "abc", "0", "10")
    svc.guardar_configuracion("Carro", 200.0, 300.0, 40)
    cfg = next(c for c in svc.obtener_configuracion() if c.tipo == "Carro")
    assert cfg.tarifa_hora == 200.0 and cfg.cupos_totales == 40


def test_cierre_registra_en_tabla(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    svc.registrar_entrada("c1", "Carro", "", "", "")
    svc.cobrar_salida("c1")
    resumen = svc.confirmar_cierre()
    assert resumen["total"] > 0

    from infrastructure import db

    with db.get_connection() as conn:
        estado = conn.execute(
            "SELECT estado_reporte FROM cierres_caja WHERE fecha=?",
            (resumen["fecha"],),
        ).fetchone()[0]
    assert estado == EstadoReporte.GENERADO.value


def test_cierre_fallido_conserva_cierre_snapshot_y_error_original(tmp_path, monkeypatch):
    from infrastructure import archivos, db, repos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    error_original = OSError("disco no disponible")

    def fallo_de_generacion(*args, **kwargs):
        raise error_original

    monkeypatch.setattr(svc, "generar_cierre_caja", fallo_de_generacion)

    with pytest.raises(OSError) as exc_info:
        svc.confirmar_cierre()

    assert exc_info.value is error_original
    with db.get_connection() as conn:
        fila = conn.execute(
            "SELECT id, estado_reporte FROM cierres_caja"
        ).fetchone()
        assert fila[1] == EstadoReporte.ERROR.value
    cierre = repos.CierreRepo().obtener_por_id(fila[0])
    assert cierre.inventario_snapshot == []


def test_reporte_existente_marca_error_y_propaga_excepcion(tmp_path, monkeypatch):
    from infrastructure import archivos, db

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    resumen = svc.obtener_resumen_cierre()
    (tmp_path / f"cierre_{resumen['fecha']}.txt").write_text(
        "REPORTE ORIGINAL", encoding="utf-8"
    )

    with pytest.raises(archivos.ReporteCierreYaExiste):
        svc.confirmar_cierre()

    with db.get_connection() as conn:
        estado = conn.execute(
            "SELECT estado_reporte FROM cierres_caja WHERE fecha=?",
            (resumen["fecha"],),
        ).fetchone()[0]
    assert estado == EstadoReporte.ERROR.value


def test_estado_pendiente_se_persiste_antes_de_generar(tmp_path, monkeypatch):
    from infrastructure import archivos, db

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    estados_observados = []

    def generar_y_observar(*args, **kwargs):
        with db.get_connection() as conn:
            estados_observados.append(
                conn.execute("SELECT estado_reporte FROM cierres_caja").fetchone()[0]
            )

    monkeypatch.setattr(svc, "generar_cierre_caja", generar_y_observar)

    svc.confirmar_cierre()

    assert estados_observados == [EstadoReporte.PENDIENTE.value]
    with db.get_connection() as conn:
        estado = conn.execute("SELECT estado_reporte FROM cierres_caja").fetchone()[0]
    assert estado == EstadoReporte.GENERADO.value


def test_transicion_generado_acepta_carrera_ganada_por_otro_proceso(monkeypatch):
    llamadas = []

    def transicion_condicional(cierre_id, estado):
        llamadas.append((cierre_id, estado))
        return False

    monkeypatch.setattr(
        svc._cierre_repo,
        "actualizar_estado_reporte_condicional",
        transicion_condicional,
    )
    monkeypatch.setattr(
        svc._cierre_repo,
        "obtener_por_id",
        lambda cierre_id: type(
            "Cierre", (), {"estado_reporte": EstadoReporte.GENERADO}
        )(),
    )

    svc._marcar_reporte_generado(42)
    assert llamadas == [(42, EstadoReporte.GENERADO)]


def test_publicacion_sin_transicion_generado_no_se_reporta_como_exitosa(
    tmp_path, monkeypatch
):
    from infrastructure import archivos, db

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    def publicar(*args, **kwargs):
        archivo = tmp_path / "cierre_2026-09-05.txt"
        archivo.write_text("PUBLICADO", encoding="utf-8")
        return archivo

    monkeypatch.setattr(svc, "generar_cierre_caja", publicar)
    monkeypatch.setattr(
        svc._cierre_repo,
        "actualizar_estado_reporte_condicional",
        lambda *args: False,
    )
    monkeypatch.setattr(
        svc._cierre_repo,
        "obtener_por_id",
        lambda cierre_id: type(
            "Cierre", (), {"estado_reporte": EstadoReporte.PENDIENTE}
        )(),
    )

    with pytest.raises(ValidacionError, match="fue publicado"):
        svc.confirmar_cierre()

    assert (tmp_path / "cierre_2026-09-05.txt").read_text(encoding="utf-8") == "PUBLICADO"
    with db.get_connection() as conn:
        assert conn.execute(
            "SELECT estado_reporte FROM cierres_caja"
        ).fetchone()[0] == EstadoReporte.PENDIENTE.value


def test_transicion_generado_fallida_no_se_ignora(monkeypatch):
    monkeypatch.setattr(
        svc._cierre_repo,
        "actualizar_estado_reporte_condicional",
        lambda *args: False,
    )
    monkeypatch.setattr(svc._cierre_repo, "obtener_por_id", lambda cierre_id: None)

    with pytest.raises(ValidacionError, match="no se pudo confirmar"):
        svc._marcar_reporte_generado(42)


def test_transicion_error_no_degrada_generado_en_una_carrera(monkeypatch):
    error_original = OSError("fallo de generación")
    monkeypatch.setattr(
        svc._cierre_repo,
        "actualizar_estado_reporte_condicional",
        lambda *args: False,
    )
    monkeypatch.setattr(
        svc._cierre_repo,
        "obtener_por_id",
        lambda cierre_id: type("Cierre", (), {"estado_reporte": EstadoReporte.GENERADO})(),
    )

    svc._marcar_reporte_error(42, error_original)
    assert not getattr(error_original, "__notes__", [])


def test_transicion_error_false_es_fallo_real_de_persistencia(monkeypatch):
    error_original = OSError("fallo de generación")
    monkeypatch.setattr(
        svc._cierre_repo,
        "actualizar_estado_reporte_condicional",
        lambda *args: False,
    )
    monkeypatch.setattr(
        svc._cierre_repo,
        "obtener_por_id",
        lambda cierre_id: type("Cierre", (), {"estado_reporte": EstadoReporte.ERROR})(),
    )

    with pytest.raises(ValidacionError, match="persistir el estado ERROR"):
        svc._marcar_reporte_error(42, error_original)


def test_fallo_de_generacion_con_fallo_al_persistir_error_conserva_error_original(
    monkeypatch,
):
    from infrastructure import db

    error_original = OSError("fallo de generación")
    monkeypatch.setattr(
        svc, "generar_cierre_caja", lambda *args, **kwargs: (_ for _ in ()).throw(error_original)
    )
    monkeypatch.setattr(
        svc._cierre_repo,
        "actualizar_estado_reporte_condicional",
        lambda *args: False,
    )
    monkeypatch.setattr(
        svc._cierre_repo,
        "obtener_por_id",
        lambda cierre_id: type("Cierre", (), {"estado_reporte": EstadoReporte.PENDIENTE})(),
    )

    with pytest.raises(OSError) as exc_info:
        svc.confirmar_cierre()

    assert exc_info.value is error_original
    assert any("No se pudo persistir ERROR" in note for note in error_original.__notes__)
    with db.get_connection() as conn:
        assert conn.execute(
            "SELECT estado_reporte FROM cierres_caja"
        ).fetchone()[0] == EstadoReporte.PENDIENTE.value


def _registrar_cierre_historico(
    estado=EstadoReporte.PENDIENTE, fecha="2026-09-04"
):
    from infrastructure import repos

    return repos.CierreRepo().registrar(
        fecha,
        175000.0,
        2,
        total_horas=100000.0,
        cantidad_horas=1,
        total_mensualidades=75000.0,
        cantidad_mensualidades=1,
        inventario_snapshot=[("HIST1", "Carro", "2026-09-04 08:00:00")],
        estado_reporte=estado,
    )


def test_recuperar_reporte_pendiente_y_error(tmp_path, monkeypatch):
    from infrastructure import archivos, db

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    pendiente = _registrar_cierre_historico()
    assert svc.recuperar_reporte_cierre(pendiente.id).exists()

    (tmp_path / "cierre_2026-09-04.txt").unlink()
    error = _registrar_cierre_historico(EstadoReporte.ERROR, "2026-09-05")
    assert svc.recuperar_reporte_cierre(error.id).exists()

    with db.get_connection() as conn:
        estados = [row[0] for row in conn.execute(
            "SELECT estado_reporte FROM cierres_caja ORDER BY id"
        )]
    assert estados == [EstadoReporte.GENERADO.value, EstadoReporte.GENERADO.value]


def test_recuperar_reporte_fallido_conserva_error_original(tmp_path, monkeypatch):
    from infrastructure import archivos, db

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    cierre = _registrar_cierre_historico(EstadoReporte.ERROR)
    error_original = OSError("filesystem no disponible")

    def fallo(*args, **kwargs):
        raise error_original

    monkeypatch.setattr(svc, "generar_cierre_caja", fallo)

    with pytest.raises(OSError) as exc_info:
        svc.recuperar_reporte_cierre(cierre.id)

    assert exc_info.value is error_original
    with db.get_connection() as conn:
        assert conn.execute(
            "SELECT estado_reporte FROM cierres_caja WHERE id=?", (cierre.id,)
        ).fetchone()[0] == EstadoReporte.ERROR.value


def test_recuperar_reporte_existente_no_sobrescribe_ni_marca_generado(tmp_path, monkeypatch):
    from infrastructure import archivos, db

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    cierre = _registrar_cierre_historico()
    archivo = tmp_path / "cierre_2026-09-04.txt"
    archivo.write_text("ORIGINAL", encoding="utf-8")

    with pytest.raises(archivos.ReporteCierreYaExiste):
        svc.recuperar_reporte_cierre(cierre.id)

    assert archivo.read_text(encoding="utf-8") == "ORIGINAL"
    with db.get_connection() as conn:
        assert conn.execute(
            "SELECT estado_reporte FROM cierres_caja WHERE id=?", (cierre.id,)
        ).fetchone()[0] == EstadoReporte.ERROR.value


def test_recuperar_reporte_rechaza_generado_inexistente_sin_snapshot_e_invalido(
    tmp_path, monkeypatch
):
    from infrastructure import archivos, repos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    generado = _registrar_cierre_historico(EstadoReporte.GENERADO)
    inexistente = 999999
    sin_snapshot = repos.CierreRepo().registrar(
        "2026-09-05", 0.0, 0, estado_reporte=EstadoReporte.ERROR
    )
    invalido = repos.CierreRepo().registrar(
        "2026-09-06", 100.0, 1,
        total_horas=100.0,
        cantidad_horas=1,
        total_mensualidades=0.0,
        cantidad_mensualidades=0,
        inventario_snapshot=[("INCOMPLETO", "Carro")],
        estado_reporte=EstadoReporte.ERROR,
    )

    with pytest.raises(ValidacionError):
        svc.recuperar_reporte_cierre(generado.id)
    with pytest.raises(CierreNoEncontrado):
        svc.recuperar_reporte_cierre(inexistente)
    with pytest.raises(CierreSinSnapshot):
        svc.recuperar_reporte_cierre(sin_snapshot.id)
    with pytest.raises(CierreSinSnapshot):
        svc.recuperar_reporte_cierre(invalido.id)
    assert list(tmp_path.iterdir()) == []


def test_recuperar_reporte_solo_cambia_estado_y_usa_snapshot_historico(
    tmp_path, monkeypatch
):
    from infrastructure import archivos, db, repos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    cierre = _registrar_cierre_historico()
    antes = repos.CierreRepo().obtener_por_id(cierre.id)
    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO ingresos (placa, tipo, entrada, estado) VALUES (?, ?, ?, ?)",
            ("ACTUAL", "Moto Hora", "2026-09-04 09:00:00", "EN SITIO"),
        )

    svc.recuperar_reporte_cierre(cierre.id)
    despues = repos.CierreRepo().obtener_por_id(cierre.id)
    contenido = (tmp_path / "cierre_2026-09-04.txt").read_text(encoding="utf-8")

    for campo in (
        "fecha", "total", "vehiculos_salida", "total_horas", "cantidad_horas",
        "total_mensualidades", "cantidad_mensualidades", "inventario_snapshot",
    ):
        assert getattr(despues, campo) == getattr(antes, campo)
    assert despues.estado_reporte == EstadoReporte.GENERADO
    assert "HIST1" in contenido
    assert "ACTUAL" not in contenido


def test_segundo_cierre_del_dia_lanza_error_y_conserva_un_registro(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    primero = svc.confirmar_cierre()

    with pytest.raises(CierreDiarioYaExiste):
        svc.confirmar_cierre()

    from infrastructure import db

    with db.get_connection() as conn:
        cantidad = conn.execute(
            "SELECT COUNT(*) FROM cierres_caja WHERE fecha=?", (primero["fecha"],)
        ).fetchone()[0]

    assert cantidad == 1


def test_cierres_de_dos_fechas_distintas_funcionan(monkeypatch, tmp_path):
    from infrastructure import archivos
    from datetime import datetime

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    fechas = iter((datetime(2026, 9, 1), datetime(2026, 9, 2)))

    class FechaFalsa:
        @classmethod
        def now(cls):
            return next(fechas)

    monkeypatch.setattr(svc, "datetime", FechaFalsa)

    primero = svc.confirmar_cierre()
    segundo = svc.confirmar_cierre()

    assert primero["fecha"] != segundo["fecha"]


def test_cierre_sin_movimientos_conserva_total_cero(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    resumen = svc.confirmar_cierre()

    assert resumen["total"] == 0.0


def test_cierre_horas_y_mensualidades_coincide_en_db_y_txt(tmp_path, monkeypatch):
    from infrastructure import archivos, db, repos

    ahora = datetime.now()
    ingreso_repo = repos.IngresoRepo()
    ingreso = ingreso_repo.registrar_entrada("mix1", "Carro", "", "", "")
    ingreso_repo.finalizar(ingreso.id, ahora, 100000.0)
    ingreso_repo.registrar_pago_mes(
        "mix2", "", "", "PAGO MES", ahora, 75000.0
    )
    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    resumen = svc.confirmar_cierre()

    with db.get_connection() as conn:
        total_db = conn.execute(
            "SELECT total FROM cierres_caja WHERE fecha=?", (resumen["fecha"],)
        ).fetchone()[0]
    contenido = (tmp_path / f"cierre_{resumen['fecha']}.txt").read_text(encoding="utf-8")

    assert total_db == 175000.0
    assert "Total Horas: $100,000" in contenido
    assert "Cantidad Horas: 1" in contenido
    assert "Total Mensualidades: $75,000" in contenido
    assert "Cantidad Mensualidades: 1" in contenido
    assert "Total General: $175,000" in contenido


def test_reporte_solo_horas(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    archivo = archivos.generar_cierre_caja(
        "2026-09-01", 100000.0, 2, 0.0, 0, 100000.0, []
    )
    contenido = archivo.read_text(encoding="utf-8")

    assert "Total Horas: $100,000" in contenido
    assert "Cantidad Horas: 2" in contenido
    assert "Total Mensualidades: $0" in contenido
    assert "Cantidad Mensualidades: 0" in contenido
    assert "Total General: $100,000" in contenido


def test_reporte_solo_mensualidades(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    archivo = archivos.generar_cierre_caja(
        "2026-09-01", 0.0, 0, 75000.0, 1, 75000.0, []
    )
    contenido = archivo.read_text(encoding="utf-8")

    assert "Total Horas: $0" in contenido
    assert "Total Mensualidades: $75,000" in contenido
    assert "Cantidad Mensualidades: 1" in contenido
    assert "Total General: $75,000" in contenido


def test_reporte_vacio_muestra_totales_cero(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    archivo = archivos.generar_cierre_caja(
        "2026-09-01", 0.0, 0, 0.0, 0, 0.0, []
    )
    contenido = archivo.read_text(encoding="utf-8")

    assert "Total Horas: $0" in contenido
    assert "Total Mensualidades: $0" in contenido
    assert "Total General: $0" in contenido


def test_reporte_nuevo_crea_directorio_y_archivo(tmp_path, monkeypatch):
    from infrastructure import archivos

    reportes = tmp_path / "reportes_cierre"
    monkeypatch.setattr(archivos, "CIERRES_DIR", reportes)

    archivo = archivos.generar_cierre_caja(
        "2026-09-03", 100.0, 1, 0.0, 0, 100.0, []
    )

    assert archivo == reportes / "cierre_2026-09-03.txt"
    assert archivo.exists()


def test_reporte_existente_lanza_error_y_conserva_contenido(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    archivo = tmp_path / "cierre_2026-09-03.txt"
    archivo.write_text("REPORTE ORIGINAL", encoding="utf-8")

    with pytest.raises(archivos.ReporteCierreYaExiste):
        archivos.generar_cierre_caja(
            "2026-09-03", 999.0, 9, 0.0, 0, 999.0, []
        )

    assert archivo.read_text(encoding="utf-8") == "REPORTE ORIGINAL"


def test_reporte_existente_no_crea_archivo_alternativo(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)
    (tmp_path / "cierre_2026-09-03.txt").write_text(
        "REPORTE ORIGINAL", encoding="utf-8"
    )

    with pytest.raises(archivos.ReporteCierreYaExiste):
        archivos.generar_cierre_caja(
            "2026-09-03", 999.0, 9, 0.0, 0, 999.0, []
        )

    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "cierre_2026-09-03.txt"
    ]


def test_error_de_archivo_no_se_traduce_como_reporte_existente(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    def fallo_de_escritura(*args, **kwargs):
        raise OSError("disco no disponible")

    monkeypatch.setattr(archivos.os, "fdopen", fallo_de_escritura)

    with pytest.raises(OSError, match="disco no disponible"):
        archivos.generar_cierre_caja(
            "2026-09-03", 100.0, 1, 0.0, 0, 100.0, []
        )


def test_fallo_de_sincronizacion_no_publica_archivo_final(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    def fallo_de_fsync(_descriptor):
        raise OSError("fallo de sincronizacion")

    monkeypatch.setattr(archivos.os, "fsync", fallo_de_fsync)

    with pytest.raises(OSError, match="fallo de sincronizacion"):
        archivos.generar_cierre_caja(
            "2026-09-03", 100.0, 1, 0.0, 0, 100.0, []
        )

    assert not (tmp_path / "cierre_2026-09-03.txt").exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_fallo_de_publicacion_no_deja_archivo_final_ni_temporal(tmp_path, monkeypatch):
    from infrastructure import archivos

    monkeypatch.setattr(archivos, "CIERRES_DIR", tmp_path)

    def fallo_de_link(_temporal, _final):
        raise OSError("fallo de publicacion")

    monkeypatch.setattr(archivos.os, "link", fallo_de_link)

    with pytest.raises(OSError, match="fallo de publicacion"):
        archivos.generar_cierre_caja(
            "2026-09-03", 100.0, 1, 0.0, 0, 100.0, []
        )

    assert not (tmp_path / "cierre_2026-09-03.txt").exists()
    assert list(tmp_path.glob("*.tmp")) == []
