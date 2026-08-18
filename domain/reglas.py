from __future__ import annotations

from datetime import datetime, timedelta

DIAS_MENSUALIDAD = 30
MARGEN_ALERTA_DIAS = 3


def calcular_horas(entrada: datetime, salida: datetime) -> int:
    """Horas facturables redondeadas hacia arriba (mínimo 1)."""
    if salida <= entrada:
        return 1
    segundos = (salida - entrada).total_seconds()
    return max(1, -(-int(segundos) // 3600))  # math.ceil sin import


def calcular_costo_por_horas(entrada: datetime, salida: datetime, tarifa_hora: float) -> float:
    return calcular_horas(entrada, salida) * float(tarifa_hora)


def fecha_vencimiento(base: datetime, dias: int = DIAS_MENSUALIDAD) -> datetime:
    return base + timedelta(days=dias)


def dias_para_vencer(vencimiento: datetime, hoy: datetime | None = None) -> int:
    hoy = hoy or datetime.now()
    return (vencimiento.date() - hoy.date()).days


def clasificar_vencimiento(
    vencimiento: datetime,
    hoy: datetime | None = None,
    margen: int = MARGEN_ALERTA_DIAS,
) -> str:
    restante = dias_para_vencer(vencimiento, hoy)
    if restante < 0:
        return "vencido"
    if restante <= margen:
        return "por_vencer"
    return "ok"
