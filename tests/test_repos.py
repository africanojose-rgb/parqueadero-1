from datetime import datetime

from infrastructure import repos


def test_registrar_y_buscar_en_sitio():
    repo = repos.IngresoRepo()
    ing = repo.registrar_entrada("abc123", "Carro", "Yamaha", "Ana", "123")
    assert ing.id is not None
    assert ing.estado.value == "EN SITIO"

    encontrado = repo.buscar_en_sitio("abc123")
    assert encontrado is not None
    assert encontrado.placa == "ABC123"


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
