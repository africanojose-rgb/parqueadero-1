from __future__ import annotations

from datetime import datetime

from domain.entities import (
    CierreCaja,
    ConfiguracionVehiculo,
    Ingreso,
    Mensualidad,
)
from domain.enums import EstadoIngreso, TipoPago
from infrastructure import db
from infrastructure._dt import fmt, parse

TIPOS_PAGO_MES = {TipoPago.PAGO_MES.value, TipoPago.RENOVACION_MES.value}


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
    def registrar_entrada(
        self, placa: str, tipo: str, marca: str, propietario: str, telefono: str
    ) -> Ingreso:
        entrada = datetime.now()
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
    def registrar(self, fecha: str, total: float, vehiculos_salida: int) -> CierreCaja:
        with db.get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO cierres_caja (fecha, total, vehiculos_salida) VALUES (?,?,?)",
                (fecha, total, vehiculos_salida),
            )
            id_ = cur.lastrowid
        return CierreCaja(id_, fecha, total, vehiculos_salida)
