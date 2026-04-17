import sqlite3

def conectar():
    return sqlite3.connect('/datos/proyectos/python/parqueadero/parqueadero.db')

def actualizar_precios_y_cupos():
    conn = conectar()
    cursor = conn.cursor()
    
    tipo = input("Tipo de vehículo a modificar (Moto/Carro/Autobus/Camion): ").capitalize()
    
    # Verificar si existe
    cursor.execute("SELECT * FROM configuracion WHERE tipo_vehiculo = ?", (tipo,))
    if not cursor.fetchone():
        print("❌ Ese tipo de vehículo no existe en la base de datos.")
        conn.close()
        return

    nueva_tarifa = float(input(f"Nueva tarifa por HORA para {tipo}: "))
    nueva_mensualidad = float(input(f"Nueva tarifa MENSUAL para {tipo}: "))
    nuevos_cupos = int(input(f"Nuevos cupos TOTALES para {tipo}: "))

    cursor.execute("""
        UPDATE configuracion 
        SET tarifa_hora = ?, tarifa_mes = ?, cupos_totales = ?
        WHERE tipo_vehiculo = ?
    """, (nueva_tarifa, nueva_mensualidad, nuevos_cupos, tipo))
    
    conn.commit()
    print(f"✅ Configuración de {tipo} actualizada.")
    conn.close()