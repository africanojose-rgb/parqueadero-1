import os
import sys
from datetime import datetime
from database import crear_tablas, conectar
from gui_dashboard import DashboardBurgos

def generar_ticket_archivo(placa, tipo, entrada, salida, horas, total):
    ruta = "/datos/proyectos/python/parqueadero/tickets/"
    try:
        if not os.path.exists(ruta):
            os.makedirs(ruta)
        
        nombre = f"{ruta}ticket_{placa}_{datetime.now().strftime('%H%M%S')}.txt"
        contenido = (
            f"==========================================\n"
            f"            CIUDAD DE BURGOS                \n"
            f"        SISTEMA DE PARQUEADERO            \n"
            f"==========================================\n"
            f"PLACA:      {placa}\n"
            f"VEHÍCULO:   {tipo}\n"
            f"ENTRADA:    {entrada}\n"
            f"SALIDA:     {salida}\n"
            f"TIEMPO:     {horas} Hora(s)\n"
            f"------------------------------------------\n"
            f"TOTAL PAGADO: ${total:,.0f}\n"
            f"==========================================\n"
            f"       ¡GRACIAS POR SU CONFIANZA!         \n"
            f"==========================================\n"
        )
        with open(nombre, "w") as f:
            f.write(contenido)
    except Exception as e:
        print(f"Error al generar ticket: {e}")

if __name__ == "__main__":
    crear_tablas()
    print("🚀 Iniciando Ciudad de Burgos...")
    app = DashboardBurgos()
    app.mainloop()