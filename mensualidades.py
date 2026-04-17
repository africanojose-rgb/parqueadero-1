import sqlite3
from datetime import datetime, timedelta

def conectar():
    return sqlite3.connect('/datos/proyectos/python/parqueadero/parqueadero.db')

def registrar_pago_mensual(placa, propietario, tipo):
    conn = conectar()
    cursor = conn.cursor()
    fecha_pago = datetime.now()
    fecha_vencimiento = fecha_pago + timedelta(days=30)
    
    cursor.execute("""
        INSERT OR REPLACE INTO mensualidades (placa, propietario, tipo, fecha_pago, fecha_vencimiento)
        VALUES (?, ?, ?, ?, ?)
    """, (placa.upper(), propietario, tipo, fecha_pago.strftime('%Y-%m-%d %H:%M:%S'), fecha_vencimiento.strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    print(f"✅ Mensualidad activada para {placa.upper()}. Vence: {fecha_vencimiento.strftime('%Y-%m-%d')}")

def alertas_mensualidades():
    conn = conectar()
    cursor = conn.cursor()
    limite = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("SELECT placa, propietario, fecha_vencimiento FROM mensualidades WHERE fecha_vencimiento <= ?", (limite,))
    alertas = cursor.fetchall()
    if alertas:
        print("\n⚠️  PRÓXIMOS VENCIMIENTOS (3 DÍAS):")
        for p, prop, f in alertas:
            print(f"   [!] {p} - {prop} | Vence: {f}")
        print("-" * 40)
    conn.close()