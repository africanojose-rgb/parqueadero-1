import sqlite3
import os
from datetime import datetime

def conectar():
    return sqlite3.connect('/datos/proyectos/python/parqueadero/parqueadero.db')

def reporte_diario():
    conn = conectar()
    cursor = conn.cursor()
    hoy = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("SELECT SUM(valor_pagado) FROM ingresos WHERE estado = 'FINALIZADO' AND salida LIKE ?", (f'{hoy}%',))
    total = cursor.fetchone()[0] or 0
    print(f"\n💰 Total recaudado hoy (Horas): ${total:,.0f}")
    conn.close()

def reporte_mensual():
    conn = conectar()
    cursor = conn.cursor()
    mes = datetime.now().strftime('%Y-%m')
    cursor.execute("SELECT SUM(valor_pagado) FROM ingresos WHERE estado = 'FINALIZADO' AND salida LIKE ?", (f'{mes}%',))
    total = cursor.fetchone()[0] or 0
    print(f"\n📅 Total acumulado del mes: ${total:,.0f}")
    conn.close()

def generar_cierre_caja():
    conn = conectar()
    cursor = conn.cursor()
    hoy = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute("SELECT SUM(valor_pagado) FROM ingresos WHERE estado = 'FINALIZADO' AND salida LIKE ?", (f'{hoy}%',))
    total_h = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT placa, tipo, entrada FROM ingresos WHERE estado = 'EN SITIO'")
    inventario = cursor.fetchall()

    ruta = "/datos/proyectos/python/parqueadero/reportes_cierre/"
    if not os.path.exists(ruta): os.makedirs(ruta)
    
    archivo = f"{ruta}cierre_{hoy}.txt"
    with open(archivo, "w") as f:
        f.write(f"CIERRE DE CAJA - {hoy}\n" + "="*30 + f"\nTotal Horas: ${total_h:,.0f}\n\nVehículos en sitio:\n")
        for p, t, e in inventario: f.write(f"- {p} ({t}) Entró: {e}\n")
    
    print(f"✅ Archivo de cierre generado en: {archivo}")
    conn.close()