from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import tempfile

from infrastructure.db import BASE_DIR

TICKETS_DIR = BASE_DIR / "tickets"
CIERRES_DIR = BASE_DIR / "reportes_cierre"


class ReporteCierreYaExiste(FileExistsError):
    """El reporte de cierre ya existe y no debe sobrescribirse."""


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


def generar_cierre_caja(
    fecha: str,
    total_horas: float,
    cantidad_horas: int,
    total_mensualidades: float,
    cantidad_mensualidades: int,
    total: float,
    inventario: list[tuple],
) -> Path:
    CIERRES_DIR.mkdir(parents=True, exist_ok=True)
    archivo = CIERRES_DIR / f"cierre_{fecha}.txt"
    lineas = [
        f"CIERRE DE CAJA - {fecha}",
        "=" * 30,
        f"Total Horas: ${total_horas:,.0f}",
        f"Cantidad Horas: {cantidad_horas}",
        "",
        f"Total Mensualidades: ${total_mensualidades:,.0f}",
        f"Cantidad Mensualidades: {cantidad_mensualidades}",
        "",
        f"Total General: ${total:,.0f}",
        "",
        "Vehículos en sitio:",
    ]
    for placa, tipo, entrada in inventario:
        lineas.append(f"- {placa} ({tipo}) Entró: {entrada}")

    temporal = None
    try:
        descriptor, temporal = tempfile.mkstemp(
            prefix=f".{archivo.name}.", suffix=".tmp", dir=CIERRES_DIR
        )
        try:
            destino = os.fdopen(descriptor, "w", encoding="utf-8")
        except Exception:
            os.close(descriptor)
            raise
        with destino:
            destino.write("\n".join(lineas) + "\n")
            destino.flush()
            os.fsync(destino.fileno())

        try:
            os.link(temporal, archivo)
        except FileExistsError as exc:
            raise ReporteCierreYaExiste(
                f"El reporte de cierre ya existe: {archivo}"
            ) from exc
        finally:
            if temporal is not None:
                try:
                    os.unlink(temporal)
                except FileNotFoundError:
                    pass
                temporal = None

        directorio = os.open(CIERRES_DIR, os.O_RDONLY)
        try:
            os.fsync(directorio)
        finally:
            os.close(directorio)
    except Exception:
        if temporal is not None:
            try:
                os.unlink(temporal)
            except FileNotFoundError:
                pass
        raise
    return archivo
