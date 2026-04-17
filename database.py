import sqlite3
import os

BASE_DIR = "/datos/proyectos/python/parqueadero"
DB_PATH = os.path.join(BASE_DIR, "parqueadero.db")

def conectar():
    return sqlite3.connect(DB_PATH)

def crear_tablas():
    if not os.path.exists(BASE_DIR): os.makedirs(BASE_DIR)
    conn = conectar()
    cursor = conn.cursor()
    
    # 1. Tabla de Ingresos (Contabilidad y Auditoría)
    cursor.execute('''CREATE TABLE IF NOT EXISTS ingresos (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        placa TEXT, tipo TEXT, marca TEXT, propietario TEXT, 
                        telefono TEXT, entrada TEXT, salida TEXT, 
                        valor_pagado REAL, estado TEXT)''')

    # 2. Tabla de Mensualidades
    cursor.execute('''CREATE TABLE IF NOT EXISTS mensualidades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        placa TEXT, marca TEXT, propietario TEXT, telefono TEXT, 
                        tipo TEXT, fecha_pago TEXT, fecha_vencimiento TEXT)''')

    # 3. Tabla de Configuración (Precios y Cupos)
    cursor.execute('''CREATE TABLE IF NOT EXISTS configuracion (
                        tipo_vehiculo TEXT PRIMARY KEY,
                        tarifa_hora REAL, cupos_totales INTEGER)''')
    
    # 4. Tabla de Cierres de Caja
    cursor.execute('''CREATE TABLE IF NOT EXISTS cierres_caja (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fecha TEXT, total REAL, vehiculos_salida INTEGER)''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    crear_tablas()