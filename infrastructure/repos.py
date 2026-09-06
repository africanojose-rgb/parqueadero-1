from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from domain.entities import (
    CierreCaja,
    ConfiguracionVehiculo,
    Ingreso,
    Mensualidad,
)
from domain.enums import EstadoIngreso, EstadoReporte, TipoPago
from infrastructure import db
from infrastructure._dt import fmt, parse

TIPOS_PAGO_MES = {TipoPago.PAGO_MES.value, TipoPago.RENOVACION_MES.value}


class IngresoActivoDuplicadoPersistenceError(Exception):
    """La base rechazó una placa ya presente como ingreso activo."""


class CierreDiarioDuplicadoPersistenceError(Exception):
    """La base rechazó un cierre para una fecha ya registrada."""


class CierreSnapshotInvalidoPersistenceError(Exception):
    """El snapshot persistido de un cierre no tiene un formato válido."""


class ConfiguracionRepo:
    def obtener_todas(self) -> list[ConfiguracionVehiculo]:
        with db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM configuracion").fetchall()
        return [
            ConfiguracionVehiculo(
                tipo=r["tipo_vehiculo"],
                tarifa_hora=r["tarifa_hora"] or 0.0,
                tarifa_mes=r["tarifa_mes"] if r["tarifa_mes"] is not None else (r["tarifa_hora"] or 0.0),
                cupos_totales=r["cupos_totales"] or 0,
            )
            for r in rows
        ]

    def obtener(self, tipo: str) -> ConfiguracionVehiculo | None:
        with db.get_connection() as conn:
            r = conn.execute(
                "SELECT * FROM configuracion WHERE tipo_vehiculo=?", (tipo,)
            ).fetchone()
        if not r:
            return None
        return ConfiguracionVehiculo(
            tipo=r["tipo_vehiculo"],
            tarifa_hora=r["tarifa_hora"] or 0.0,
            tarifa_mes=r["tarifa_mes"] if r["tarifa_mes"] is not None else (r["tarifa_hora"] or 0.0),
            cupos_totales=r["cupos_totales"] or 0,
        )

    def guardar(self, cfg: ConfiguracionVehiculo) -> None:
        with db.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO configuracion
                   (tipo_vehiculo, tarifa_hora, tarifa_mes, cupos_totales)
                   VALUES (?,?,?,?)""",
                (cfg.tipo, cfg.tarifa_hora, cfg.tarifa_mes, cfg.cupos_totales),
            )


class IngresoRepo:
    def existe_en_sitio(self, placa: str) -> bool:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM ingresos WHERE placa=? AND estado=? LIMIT 1",
                (placa.upper(), EstadoIngreso.EN_SITIO.value),
            ).fetchone()
        return row is not None

    def registrar_entrada(
        self, placa: str, tipo: str, marca: str, propietario: str, telefono: str
    ) -> Ingreso:
        entrada = datetime.now()
        try:
            with db.get_connection() as conn:
                cur = conn.execute(
                    """INSERT INTO ingresos
                       (placa, tipo, marca, propietario, telefono, entrada, estado)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        placa.upper(),
                        tipo,
                        marca.upper(),
                        propietario,
                        telefono,
                        fmt(entrada),
                        EstadoIngreso.EN_SITIO.value,
                    ),
                )
                id_ = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            if (
                exc.sqlite_errorname == "SQLITE_CONSTRAINT_UNIQUE"
                and "ingresos.placa" in str(exc)
            ):
                raise IngresoActivoDuplicadoPersistenceError from exc
            raise
        return Ingreso(id_, placa.upper(), tipo, marca.upper(), propietario,
                       telefono, entrada, None, 0.0, EstadoIngreso.EN_SITIO)

    def buscar_en_sitio(self, placa: str) -> Ingreso | None:
        with db.get_connection() as conn:
            r = conn.execute(
                "SELECT * FROM ingresos WHERE placa=? AND estado=? ORDER BY id DESC LIMIT 1",
                (placa.upper(), EstadoIngreso.EN_SITIO.value),
            ).fetchone()
        return self._a_entidad(r) if r else None

    def obtener_por_id(self, id_: int) -> Ingreso | None:
        with db.get_connection() as conn:
            r = conn.execute("SELECT * FROM ingresos WHERE id=?", (id_,)).fetchone()
        return self._a_entidad(r) if r else None

    def finalizar(self, id_: int, salida: datetime, valor: float) -> None:
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE ingresos SET salida=?, valor_pagado=?, estado=? WHERE id=?",
                (fmt(salida), valor, EstadoIngreso.FINALIZADO.value, id_),
            )

    def registrar_pago_mes(
        self, placa: str, marca: str, propietario: str, tipo_pago: str, fecha: str, valor: float
    ) -> None:
        with db.get_connection() as conn:
            conn.execute(
                """INSERT INTO ingresos
                   (placa, tipo, marca, propietario, entrada, salida, valor_pagado, estado)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    placa.upper(),
                    tipo_pago,
                    marca.upper(),
                    propietario,
                    fmt(fecha),
                    fmt(fecha),
                    valor,
                    EstadoIngreso.FINALIZADO.value,
                ),
            )

    def listar_en_sitio(self) -> list[Ingreso]:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM ingresos WHERE estado=?", (EstadoIngreso.EN_SITIO.value,)
            ).fetchall()
        return [self._a_entidad(r) for r in rows]

    def contar_en_sitio_por_tipo(self) -> dict[str, int]:
        with db.get_connection() as conn:
            rows = conn.execute(
                "SELECT tipo, COUNT(*) c FROM ingresos WHERE estado=? GROUP BY tipo",
                (EstadoIngreso.EN_SITIO.value,),
            ).fetchall()
        return {r["tipo"]: r["c"] for r in rows}

    def resumen_dia(self, hoy: str) -> dict:
        with db.get_connection() as conn:
            filtro = f"{hoy}%"
            h = conn.execute(
                """SELECT SUM(valor_pagado), COUNT(*) FROM ingresos
                   WHERE estado=? AND salida LIKE ? AND tipo NOT IN (%s)"""
                % ",".join("?" * len(TIPOS_PAGO_MES)),
                (EstadoIngreso.FINALIZADO.value, filtro, *TIPOS_PAGO_MES),
            ).fetchone()
            m = conn.execute(
                """SELECT SUM(valor_pagado), COUNT(*) FROM ingresos
                   WHERE estado=? AND salida LIKE ? AND tipo IN (%s)"""
                % ",".join("?" * len(TIPOS_PAGO_MES)),
                (EstadoIngreso.FINALIZADO.value, filtro, *TIPOS_PAGO_MES),
            ).fetchone()
        return {
            "horas_total": h[0] or 0.0,
            "horas_count": h[1] or 0,
            "mes_total": m[0] or 0.0,
            "mes_count": m[1] or 0,
        }

    def sumar_valor_pagado_hoy(self, hoy: str) -> float:
        with db.get_connection() as conn:
            r = conn.execute(
                "SELECT SUM(valor_pagado) FROM ingresos WHERE estado=? AND salida LIKE ?",
                (EstadoIngreso.FINALIZADO.value, f"{hoy}%"),
            ).fetchone()
        return r[0] or 0.0

    @staticmethod
    def _a_entidad(r) -> Ingreso:
        return Ingreso(
            id=r["id"],
            placa=r["placa"],
            tipo=r["tipo"],
            marca=r["marca"],
            propietario=r["propietario"],
            telefono=r["telefono"],
            entrada=parse(r["entrada"]),
            salida=parse(r["salida"]) if r["salida"] else None,
            valor_pagado=r["valor_pagado"] or 0.0,
            estado=EstadoIngreso(r["estado"]),
        )


class MensualidadRepo:
    def registrar(
        self, placa, marca, propietario, telefono, tipo, fecha_pago, fecha_vencimiento
    ) -> Mensualidad:
        with db.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO mensualidades
                   (placa, marca, propietario, telefono, tipo, fecha_pago, fecha_vencimiento)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    placa.upper(),
                    marca.upper(),
                    propietario,
                    telefono,
                    tipo,
                    fmt(fecha_pago),
                    fmt(fecha_vencimiento),
                ),
            )
        return Mensualidad(None, placa.upper(), marca.upper(), propietario,
                           telefono, tipo, fecha_pago, fecha_vencimiento)

    def listar(self) -> list[Mensualidad]:
        with db.get_connection() as conn:
            rows = conn.execute("SELECT * FROM mensualidades").fetchall()
        return [self._a_entidad(r) for r in rows]

    def obtener_por_placa(self, placa: str) -> Mensualidad | None:
        with db.get_connection() as conn:
            r = conn.execute(
                "SELECT * FROM mensualidades WHERE placa=?", (placa.upper(),)
            ).fetchone()
        return self._a_entidad(r) if r else None

    def eliminar(self, placa: str) -> None:
        with db.get_connection() as conn:
            conn.execute("DELETE FROM mensualidades WHERE placa=?", (placa.upper(),))

    def renovar(self, placa: str, nueva_fecha_pago: datetime, nueva_fecha_venc: datetime) -> None:
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE mensualidades SET fecha_pago=?, fecha_vencimiento=? WHERE placa=?",
                (fmt(nueva_fecha_pago), fmt(nueva_fecha_venc), placa.upper()),
            )

    @staticmethod
    def _a_entidad(r) -> Mensualidad:
        return Mensualidad(
            id=r["id"],
            placa=r["placa"],
            marca=r["marca"],
            propietario=r["propietario"],
            telefono=r["telefono"],
            tipo=r["tipo"],
            fecha_pago=parse(r["fecha_pago"]),
            fecha_vencimiento=parse(r["fecha_vencimiento"]),
        )


class CierreRepo:
    def existe_por_fecha(self, fecha: str) -> bool:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM cierres_caja WHERE fecha=? LIMIT 1", (fecha,)
            ).fetchone()
        return row is not None

    def registrar(
        self,
        fecha: str,
        total: float,
        vehiculos_salida: int,
        *,
        total_horas: float | None = None,
        cantidad_horas: int | None = None,
        total_mensualidades: float | None = None,
        cantidad_mensualidades: int | None = None,
        inventario_snapshot: list[tuple] | None = None,
        estado_reporte: EstadoReporte | None = None,
    ) -> CierreCaja:
        snapshot = (
            json.dumps(
                [list(item) for item in inventario_snapshot],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if inventario_snapshot is not None
            else None
        )
        try:
            with db.get_connection() as conn:
                cur = conn.execute(
                    """INSERT INTO cierres_caja
                       (fecha, total, vehiculos_salida, total_horas, cantidad_horas,
                        total_mensualidades, cantidad_mensualidades, inventario_snapshot,
                        estado_reporte)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        fecha,
                        total,
                        vehiculos_salida,
                        total_horas,
                        cantidad_horas,
                        total_mensualidades,
                        cantidad_mensualidades,
                        snapshot,
                        estado_reporte.value if estado_reporte is not None else None,
                    ),
                )
                id_ = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            if (
                getattr(exc, "sqlite_errorname", None) == "SQLITE_CONSTRAINT_UNIQUE"
                and "cierres_caja.fecha" in str(exc)
            ):
                raise CierreDiarioDuplicadoPersistenceError from exc
            raise
        return CierreCaja(
            id_,
            fecha,
            total,
            vehiculos_salida,
            total_horas,
            cantidad_horas,
            total_mensualidades,
            cantidad_mensualidades,
            inventario_snapshot,
            estado_reporte,
        )

    def obtener_por_id(self, cierre_id: int) -> CierreCaja | None:
        with db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM cierres_caja WHERE id=?", (cierre_id,)
            ).fetchone()
        if not row:
            return None
        try:
            snapshot = (
                [tuple(item) for item in json.loads(row["inventario_snapshot"])]
                if row["inventario_snapshot"] is not None
                else None
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CierreSnapshotInvalidoPersistenceError from exc
        try:
            estado_reporte = (
                EstadoReporte(row["estado_reporte"])
                if row["estado_reporte"] is not None
                else None
            )
        except ValueError as exc:
            raise ValueError("Estado de reporte no válido") from exc
        return CierreCaja(
            id=row["id"],
            fecha=row["fecha"],
            total=row["total"],
            vehiculos_salida=row["vehiculos_salida"],
            total_horas=row["total_horas"],
            cantidad_horas=row["cantidad_horas"],
            total_mensualidades=row["total_mensualidades"],
            cantidad_mensualidades=row["cantidad_mensualidades"],
            inventario_snapshot=snapshot,
            estado_reporte=estado_reporte,
        )

    def actualizar_estado_reporte_condicional(
        self,
        cierre_id: int,
        estado_reporte: EstadoReporte,
    ) -> bool:
        if estado_reporte not in (EstadoReporte.GENERADO, EstadoReporte.ERROR):
            raise ValueError("Transición de estado de reporte no permitida")
        with db.get_connection() as conn:
            cursor = conn.execute(
                """UPDATE cierres_caja SET estado_reporte=?
                   WHERE id=? AND estado_reporte IN (?, ?)""",
                (
                    estado_reporte.value,
                    cierre_id,
                    EstadoReporte.PENDIENTE.value,
                    EstadoReporte.ERROR.value,
                ),
            )
        return cursor.rowcount == 1
