from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.enums import EstadoIngreso, EstadoReporte, TipoVehiculo


@dataclass
class ConfiguracionVehiculo:
    tipo: str
    tarifa_hora: float
    tarifa_mes: float
    cupos_totales: int


@dataclass
class Ingreso:
    id: int | None
    placa: str
    tipo: str
    marca: str
    propietario: str
    telefono: str
    entrada: datetime
    salida: datetime | None
    valor_pagado: float
    estado: EstadoIngreso


@dataclass
class Mensualidad:
    id: int | None
    placa: str
    marca: str
    propietario: str
    telefono: str
    tipo: str
    fecha_pago: datetime
    fecha_vencimiento: datetime


@dataclass
class CierreCaja:
    id: int | None
    fecha: str
    total: float
    vehiculos_salida: int
    total_horas: float | None = None
    cantidad_horas: int | None = None
    total_mensualidades: float | None = None
    cantidad_mensualidades: int | None = None
    inventario_snapshot: list[tuple] | None = None
    estado_reporte: EstadoReporte | None = None
