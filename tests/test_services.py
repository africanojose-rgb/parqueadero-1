import pytest

import services.casos_uso as svc
from services.exceptions import ConfiguracionFaltante, ValidacionError


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


def test_cierre_registra_en_tabla():
    svc.registrar_entrada("c1", "Carro", "", "", "")
    svc.cobrar_salida("c1")
    resumen = svc.confirmar_cierre()
    assert resumen["total"] > 0
