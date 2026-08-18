from datetime import datetime, timedelta

from domain import reglas


def test_calcular_horas_minimo_una():
    entrada = datetime(2026, 1, 1, 10, 0)
    assert reglas.calcular_horas(entrada, entrada + timedelta(minutes=5)) == 1


def test_calcular_horas_redondea_hacia_arriba():
    entrada = datetime(2026, 1, 1, 10, 0)
    assert reglas.calcular_horas(entrada, entrada + timedelta(hours=2, minutes=1)) == 3


def test_calcular_horas_salida_anterior_devuelve_uno():
    entrada = datetime(2026, 1, 1, 10, 0)
    assert reglas.calcular_horas(entrada, entrada - timedelta(hours=1)) == 1


def test_calcular_costo():
    entrada = datetime(2026, 1, 1, 10, 0)
    salida = entrada + timedelta(hours=3)
    assert reglas.calcular_costo_por_horas(entrada, salida, 1000.0) == 3000.0


def test_fecha_vencimiento():
    base = datetime(2026, 1, 1)
    assert reglas.fecha_vencimiento(base) == base + timedelta(days=30)


def test_clasificar_vencimiento():
    hoy = datetime(2026, 6, 1)
    assert reglas.clasificar_vencimiento(hoy - timedelta(days=1), hoy) == "vencido"
    assert reglas.clasificar_vencimiento(hoy + timedelta(days=2), hoy) == "por_vencer"
    assert reglas.clasificar_vencimiento(hoy + timedelta(days=10), hoy) == "ok"
