from __future__ import annotations

from enum import Enum


class EstadoIngreso(str, Enum):
    EN_SITIO = "EN SITIO"
    FINALIZADO = "FINALIZADO"


class TipoVehiculo(str, Enum):
    MOTO_HORA = "Moto Hora"
    MOTO_MES = "Moto Mes"
    CARRO = "Carro"
    CARRO_MES = "Carro Mes"
    CAMION = "Camion"
    AUTOBUS = "Autobus"
    OTROS_MES = "Otros Mes"


# Tipos de pago mensual (se cobran con tarifa_mes)
TIPOS_MENSUALES = {
    TipoVehiculo.MOTO_MES,
    TipoVehiculo.CARRO_MES,
    TipoVehiculo.OTROS_MES,
}

# Tipos facturables por hora (se cobran con tarifa_hora)
TIPOS_HORA = {
    TipoVehiculo.MOTO_HORA,
    TipoVehiculo.CARRO,
    TipoVehiculo.CAMION,
    TipoVehiculo.AUTOBUS,
}


class TipoPago(str, Enum):
    PAGO_MES = "PAGO MES"
    RENOVACION_MES = "RENOVACIÓN MES"


def es_mensual(tipo: str) -> bool:
    return tipo in {t.value for t in TIPOS_MENSUALES} or tipo in {
        TipoPago.PAGO_MES.value,
        TipoPago.RENOVACION_MES.value,
    }
