from __future__ import annotations

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
_default_db = BASE_DIR / "parqueadero.db"
DB_PATH = Path(os.environ.get("PARQUEADERO_DB", _default_db))

# Claves de configuración por defecto (tipo, tarifa_hora, tarifa_mes, cupos)
CONFIG_DEFECTO = [
    ("Moto Hora", 1000.0, 75000.0, 50),
    ("Moto Mes", 75000.0, 75000.0, 100),
    ("Carro", 165000.0, 1_650_000.0, 50),
    ("Carro Mes", 1_650_000.0, 1_650_000.0, 50),
    ("Camion", 200000.0, 2_000_000.0, 20),
    ("Autobus", 250000.0, 2_500_000.0, 20),
    ("Otros Mes", 100000.0, 100000.0, 30),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def crear_tablas() -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS ingresos (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   placa TEXT, tipo TEXT, marca TEXT, propietario TEXT,
                   telefono TEXT, entrada TEXT, salida TEXT,
                   valor_pagado REAL, estado TEXT)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS mensualidades (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   placa TEXT, marca TEXT, propietario TEXT, telefono TEXT,
                   tipo TEXT, fecha_pago TEXT, fecha_vencimiento TEXT)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS configuracion (
                   tipo_vehiculo TEXT PRIMARY KEY,
                   tarifa_hora REAL, tarifa_mes REAL, cupos_totales INTEGER)"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS cierres_caja (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   fecha TEXT, total REAL, vehiculos_salida INTEGER)"""
        )

        cur.execute("PRAGMA table_info(cierres_caja)")
        columnas_cierre = {row["name"] for row in cur.fetchall()}
        for columna, tipo in (
            ("total_horas", "REAL"),
            ("cantidad_horas", "INTEGER"),
            ("total_mensualidades", "REAL"),
            ("cantidad_mensualidades", "INTEGER"),
            ("inventario_snapshot", "TEXT"),
            ("estado_reporte", "TEXT"),
        ):
            if columna not in columnas_cierre:
                cur.execute(f"ALTER TABLE cierres_caja ADD COLUMN {columna} {tipo}")

        cierres_duplicados = cur.execute(
            """SELECT fecha, COUNT(*) AS cantidad, GROUP_CONCAT(id) AS ids
               FROM cierres_caja
               GROUP BY fecha
               HAVING COUNT(*) > 1"""
        ).fetchall()
        if cierres_duplicados:
            detalle = "; ".join(
                f"fecha={row['fecha']!r}, cantidad={row['cantidad']}, ids={row['ids']}"
                for row in cierres_duplicados
            )
            raise RuntimeError(
                "No se puede crear la restricción de cierres diarios duplicados: "
                f"{detalle}. Resuelva los conflictos manualmente sin eliminar datos automáticamente."
            )

        # Migración: asegurar columna tarifa_mes en DBs existentes
        cur.execute("PRAGMA table_info(configuracion)")
        columnas = {row["name"] for row in cur.fetchall()}
        if "tarifa_mes" not in columnas:
            cur.execute("ALTER TABLE configuracion ADD COLUMN tarifa_mes REAL")

        duplicados = cur.execute(
            """SELECT placa, COUNT(*) AS cantidad, GROUP_CONCAT(id) AS ids
               FROM ingresos
               WHERE estado=?
               GROUP BY placa
               HAVING COUNT(*) > 1""",
            ("EN SITIO",),
        ).fetchall()
        if duplicados:
            detalle = "; ".join(
                f"placa={row['placa']!r}, cantidad={row['cantidad']}, ids={row['ids']}"
                for row in duplicados
            )
            raise RuntimeError(
                "No se puede crear la restricción de ingresos activos duplicados: "
                f"{detalle}. Resuelva los conflictos manualmente sin eliminar datos automáticamente."
            )

        cur.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS ux_ingresos_placa_en_sitio
               ON ingresos(placa)
               WHERE estado='EN SITIO'"""
        )
        cur.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS ux_cierres_caja_fecha
               ON cierres_caja(fecha)"""
        )
        conn.commit()
    finally:
        conn.close()


def sembrar_configuracion() -> None:
    conn = get_connection()
    cur = conn.cursor()
    for tipo, th, tm, cupos in CONFIG_DEFECTO:
        cur.execute(
            """INSERT OR IGNORE INTO configuracion
               (tipo_vehiculo, tarifa_hora, tarifa_mes, cupos_totales)
               VALUES (?,?,?,?)""",
            (tipo, th, tm, cupos),
        )
    # Rellenar tarifa_mes donde quede nula (compatibilidad con datos previos)
    cur.execute(
        "UPDATE configuracion SET tarifa_mes = tarifa_hora WHERE tarifa_mes IS NULL"
    )
    conn.commit()
    conn.close()


def inicializar() -> None:
    crear_tablas()
    sembrar_configuracion()
