from __future__ import annotations

from datetime import datetime
from pathlib import Path

from infrastructure.db import BASE_DIR

TICKETS_DIR = BASE_DIR / "tickets"
CIERRES_DIR = BASE_DIR / "reportes_cierre"


def generar_ticket(
    placa: str, tipo: str, entrada: str, salida: str, horas: int, total: float
) -> Path:
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)
    nombre = TICKETS_DIR / f"ticket_{placa}_{datetime.now():%H%M%S}.txt"
    contenido = (
        "================================\n"
        "        CIUDAD DE BURGOS        \n"
        "    SISTEMA DE PARQUEADERO      \n"
        "================================\n"
        f"PLACA:      {placa}\n"
        f"VEHÍCULO:   {tipo}\n"
        f"ENTRADA:    {entrada}\n"
        f"SALIDA:     {salida}\n"
        f"TIEMPO:     {horas} Hora(s)\n"
        "--------------------------------\n"
        f"TOTAL PAGADO: ${total:,.0f}\n"
        "================================\n"
        "   ¡GRACIAS POR SU CONFIANZA!   \n"
        "================================\n"
    )
    nombre.write_text(contenido, encoding="utf-8")
    return nombre


def generar_cierre_caja(fecha: str, total_horas: float, inventario: list[tuple]) -> Path:
    CIERRES_DIR.mkdir(parents=True, exist_ok=True)
    archivo = CIERRES_DIR / f"cierre_{fecha}.txt"
    lineas = [
        f"CIERRE DE CAJA - {fecha}",
        "=" * 30,
        f"Total Horas: ${total_horas:,.0f}",
        "",
        "Vehículos en sitio:",
    ]
    for placa, tipo, entrada in inventario:
        lineas.append(f"- {placa} ({tipo}) Entró: {entrada}")
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo
