import sys
import os
import math
from datetime import datetime, timedelta
import customtkinter as ctk
from tkinter import ttk, messagebox

# Configuración de rutas
sys.path.append("/datos/proyectos/python/parqueadero")
from database import conectar

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DashboardBurgos(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CIUDAD BURGOS v3.3 - Gestión Total")
        self.geometry("1300x850")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- BARRA LATERAL ---
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar, text="CIUDAD\nBURGOS", font=("Roboto", 24, "bold")).pack(pady=20)

        self.entry_busqueda = ctk.CTkEntry(self.sidebar, placeholder_text="PLACA...", width=180)
        self.entry_busqueda.pack(pady=10)
        ctk.CTkButton(self.sidebar, text="🔍 BUSCAR", command=self.buscar_placa, fg_color="#34495e").pack(pady=5)

        self.btn_menu("➕ ENTRADA HORA", self.abrir_ventana_ingreso)
        self.btn_menu("➖ SALIDA / COBRO", self.abrir_ventana_salida)
        self.btn_menu("📅 REGISTRAR MES", self.abrir_ventana_mensualidad)
        self.btn_menu("📊 REPORTES", self.abrir_ventana_reportes)
        self.btn_menu("🔒 CIERRE DE CAJA", self.abrir_ventana_cierre)
        self.btn_menu("⚙️ CONFIGURACIÓN", self.abrir_ventana_config)

        # --- PANEL PRINCIPAL ---
        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.grid(row=0, column=1, padx=25, pady=20, sticky="nsew")

        # KPIs
        self.kpi_frame = ctk.CTkFrame(self.main_view, fg_color="transparent")
        self.kpi_frame.pack(fill="x", pady=15)
        self.card_m_hora = self.crear_card(self.kpi_frame, "MOTOS HORA", "#3498db")
        self.card_m_mes = self.crear_card(self.kpi_frame, "MOTOS MES", "#9b59b6")
        self.card_otros = self.crear_card(self.kpi_frame, "CARROS/OTROS", "#2ecc71")
        self.card_vencidos = self.crear_card(self.kpi_frame, "ALERTAS MES", "#e67e22")

        self.tabs_info = ctk.CTkTabview(self.main_view)
        self.tabs_info.pack(fill="both", expand=True)
        self.tabs_info.add("Mensualidades")
        self.tabs_info.add("Vehículos en Sitio")

        self.setup_tablas()
        self.refrescar_datos()

    def btn_menu(self, txt, cmd):
        btn = ctk.CTkButton(self.sidebar, text=txt, command=cmd, height=45, fg_color="transparent", border_width=1)
        btn.pack(pady=8, padx=20, fill="x")

    def crear_card(self, master, tit, col):
        f = ctk.CTkFrame(master, fg_color=col, corner_radius=12)
        f.pack(side="left", padx=5, expand=True, fill="both")
        lbl = ctk.CTkLabel(f, text="0 / 0", font=("Roboto", 22, "bold"), text_color="white")
        lbl.pack(pady=(15,5))
        ctk.CTkLabel(f, text=tit, font=("Roboto", 10), text_color="white").pack(pady=(0,10))
        return lbl

    def setup_tablas(self):
        # Tabla Mensualidades
        self.tabla_m = ttk.Treeview(self.tabs_info.tab("Mensualidades"), columns=("P", "M", "D", "T", "V", "E"), show="headings")
        for c, h in zip(("P", "M", "D", "T", "V", "E"), ("PLACA", "MARCA", "DUEÑO", "TELÉFONO", "VENCE", "TIPO")):
            self.tabla_m.heading(c, text=h); self.tabla_m.column(c, anchor="center")
        self.tabla_m.tag_configure('vencido', background='#721c24', foreground='white')
        self.tabla_m.tag_configure('por_vencer', background='#856404', foreground='white')
        self.tabla_m.pack(fill="both", expand=True)
        
        btn_m_frame = ctk.CTkFrame(self.tabs_info.tab("Mensualidades"), fg_color="transparent")
        btn_m_frame.pack(pady=10)
        ctk.CTkButton(btn_m_frame, text="🔄 RENOVAR MES", fg_color="#27ae60", command=self.proceso_renovacion).pack(side="left", padx=10)
        ctk.CTkButton(btn_m_frame, text="🗑️ DAR DE BAJA", fg_color="#e74c3c", command=self.eliminar_mensualidad).pack(side="left", padx=10)

        # Tabla Sitio
        self.tabla_s = ttk.Treeview(self.tabs_info.tab("Vehículos en Sitio"), columns=("P", "M", "T", "D", "E"), show="headings")
        for c, h in zip(("P", "M", "T", "D", "E"), ("PLACA", "MARCA", "TIPO", "DUEÑO", "ENTRADA")):
            self.tabla_s.heading(c, text=h); self.tabla_s.column(c, anchor="center")
        self.tabla_s.pack(fill="both", expand=True)

    def buscar_placa(self):
        placa = self.entry_busqueda.get().strip().upper()
        if not placa: return
        conn = conectar(); cursor = conn.cursor()
        cursor.execute("SELECT placa, marca, tipo, propietario, estado FROM ingresos WHERE placa=? ORDER BY id DESC LIMIT 1", (placa,))
        r = cursor.fetchone()
        conn.close()
        if r: messagebox.showinfo("Resultado", f"PLACA: {r[0]}\nMARCA: {r[1]}\nTIPO: {r[2]}\nESTADO: {r[4]}")
        else: messagebox.showwarning("Buscador", "No hay registros de esa placa.")

    def abrir_ventana_ingreso(self):
        win = ctk.CTkToplevel(self); win.geometry("400x600"); win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="ENTRADA HORA", font=("Roboto", 18, "bold")).pack(pady=20)
        p = ctk.CTkEntry(win, placeholder_text="PLACA", width=250)
        m = ctk.CTkEntry(win, placeholder_text="MARCA", width=250)
        d = ctk.CTkEntry(win, placeholder_text="DUEÑO", width=250)
        t = ctk.CTkEntry(win, placeholder_text="TELÉFONO", width=250)
        v = ctk.CTkComboBox(win, values=["Moto Hora", "Carro", "Camion", "Autobus"], width=250)
        for widget in [p, m, d, t, v]: widget.pack(pady=10)

        def guardar():
            placa = p.get().strip().upper()
            if not placa: return
            conn = conectar(); cursor = conn.cursor()
            cursor.execute("INSERT INTO ingresos (placa, tipo, marca, propietario, telefono, entrada, estado) VALUES (?,?,?,?,?,?,?)",
                           (placa, v.get(), m.get().upper(), d.get(), t.get(), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'EN SITIO'))
            conn.commit(); conn.close(); win.destroy(); self.refrescar_datos()
        ctk.CTkButton(win, text="REGISTRAR ENTRADA", fg_color="#2ecc71", command=guardar).pack(pady=20)

    def abrir_ventana_mensualidad(self):
        win = ctk.CTkToplevel(self); win.geometry("400x650"); win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="NUEVO PAGO MENSUAL", font=("Roboto", 18, "bold")).pack(pady=20)
        p = ctk.CTkEntry(win, placeholder_text="PLACA", width=250)
        m = ctk.CTkEntry(win, placeholder_text="MARCA", width=250)
        d = ctk.CTkEntry(win, placeholder_text="PROPIETARIO", width=250)
        t = ctk.CTkEntry(win, placeholder_text="TELÉFONO", width=250)
        v = ctk.CTkComboBox(win, values=["Moto Mes", "Carro Mes", "Otros Mes"], width=250)
        for widget in [p, m, d, t, v]: widget.pack(pady=10)
        
        def guardar_mes():
            placa = p.get().strip().upper()
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f_vence = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            conn = conectar(); cursor = conn.cursor()
            cursor.execute("SELECT tarifa_hora FROM configuracion WHERE tipo_vehiculo=?", (v.get(),))
            res_t = cursor.fetchone()
            precio = res_t[0] if res_t else 0
            
            cursor.execute("INSERT INTO mensualidades (placa, marca, propietario, telefono, tipo, fecha_pago, fecha_vencimiento) VALUES (?,?,?,?,?,?,?)",
                           (placa, m.get().upper(), d.get(), t.get(), v.get(), ahora, f_vence))
            cursor.execute("INSERT INTO ingresos (placa, tipo, marca, propietario, entrada, salida, valor_pagado, estado) VALUES (?,?,?,?,?,?,?,?)",
                           (placa, "PAGO MES", m.get().upper(), d.get(), ahora, ahora, precio, 'FINALIZADO'))
            conn.commit(); conn.close(); win.destroy(); self.refrescar_datos()
            messagebox.showinfo("Éxito", f"Mensualidad activada para {placa}")
        ctk.CTkButton(win, text="COBRAR Y ACTIVAR", fg_color="#9b59b6", command=guardar_mes).pack(pady=20)

    def proceso_renovacion(self):
        selected = self.tabla_m.focus()
        if not selected: return messagebox.showwarning("Atención", "Seleccione un cliente.")
        v = self.tabla_m.item(selected, 'values')
        if not messagebox.askyesno("Confirmar", f"¿Renovar placa {v[0]}?"): return
        
        conn = conectar(); cursor = conn.cursor()
        cursor.execute("SELECT tarifa_hora FROM configuracion WHERE tipo_vehiculo=?", (v[5],))
        res_t = cursor.fetchone()
        precio = res_t[0] if res_t else 0
        base = max(datetime.now(), datetime.strptime(v[4], '%Y-%m-%d %H:%M:%S'))
        nueva_f = (base + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("UPDATE mensualidades SET fecha_pago=?, fecha_vencimiento=? WHERE placa=?", (ahora, nueva_f, v[0]))
        cursor.execute("INSERT INTO ingresos (placa, tipo, marca, propietario, entrada, salida, valor_pagado, estado) VALUES (?,?,?,?,?,?,?,?)",
                       (v[0], "RENOVACIÓN MES", v[1], v[2], ahora, ahora, precio, 'FINALIZADO'))
        conn.commit(); conn.close(); self.refrescar_datos()
        messagebox.showinfo("OK", "Renovación exitosa y registrada en caja.")

    def eliminar_mensualidad(self):
        selected = self.tabla_m.focus()
        if not selected: return messagebox.showwarning("Atención", "Seleccione un registro.")
        placa = self.tabla_m.item(selected, 'values')[0]
        if messagebox.askyesno("Baja", f"¿Eliminar mensualidad de {placa}?"):
            conn = conectar(); cursor = conn.cursor()
            cursor.execute("DELETE FROM mensualidades WHERE placa=?", (placa,))
            conn.commit(); conn.close(); self.refrescar_datos()

    def abrir_ventana_cierre(self):
        win = ctk.CTkToplevel(self); win.geometry("500x650")
        ctk.CTkLabel(win, text="CORTE DE CAJA DETALLADO", font=("Roboto", 20, "bold")).pack(pady=20)
        conn = conectar(); cursor = conn.cursor()
        hoy = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("SELECT SUM(valor_pagado), COUNT(*) FROM ingresos WHERE salida LIKE ? AND tipo NOT LIKE '%MES%'", (f'{hoy}%',))
        res_h = cursor.fetchone()
        cursor.execute("SELECT SUM(valor_pagado), COUNT(*) FROM ingresos WHERE salida LIKE ? AND tipo LIKE '%MES%'", (f'{hoy}%',))
        res_m = cursor.fetchone()
        
        t_h, c_h = (res_h[0] or 0), (res_h[1] or 0)
        t_m, c_m = (res_m[0] or 0), (res_m[1] or 0)
        
        info = f"FECHA: {hoy}\n\nHORAS: {c_h} vehículos | ${t_h:,.0f}\nMESES: {c_m} pagos | ${t_m:,.0f}\n\nTOTAL GENERAL: ${t_h+t_m:,.0f}"
        ctk.CTkLabel(win, text=info, font=("Courier", 18), justify="left").pack(pady=30)
        
        def confirmar():
            cursor.execute("INSERT INTO cierres_caja (fecha, total, vehiculos_salida) VALUES (?,?,?)", (hoy, t_h+t_m, c_h+c_m))
            conn.commit(); conn.close(); win.destroy()
            messagebox.showinfo("Cierre", "Caja cerrada correctamente.")
        ctk.CTkButton(win, text="CONFIRMAR CIERRE", fg_color="#e74c3c", command=confirmar).pack(pady=20)

    def abrir_ventana_salida(self):
        win = ctk.CTkToplevel(self); win.geometry("400x500"); win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="COBRAR SALIDA", font=("Roboto", 18, "bold")).pack(pady=20)
        ent_p = ctk.CTkEntry(win, placeholder_text="PLACA", width=250); ent_p.pack(pady=10)
        lbl = ctk.CTkLabel(win, text="..."); lbl.pack(pady=10)

        def calcular():
            placa = ent_p.get().strip().upper()
            conn = conectar(); cursor = conn.cursor()
            cursor.execute("SELECT id, entrada, tipo, marca FROM ingresos WHERE placa=? AND estado='EN SITIO'", (placa,))
            r = cursor.fetchone()
            if r:
                h = math.ceil((datetime.now() - datetime.strptime(r[1], '%Y-%m-%d %H:%M:%S')).total_seconds()/3600)
                cursor.execute("SELECT tarifa_hora FROM configuracion WHERE tipo_vehiculo=?", (r[2],))
                res_t = cursor.fetchone()
                tarifa = res_t[0] if res_t else 2000
                total = h * tarifa
                lbl.configure(text=f"MARCA: {r[3]}\nHORAS: {h}\nTOTAL: ${total:,.0f}")
                btn_f.configure(state="normal", command=lambda: self.finalizar_salida(r[0], total, placa, r[2], r[1], h, win))
            else: lbl.configure(text="❌ No encontrado en sitio")
            conn.close()

        ctk.CTkButton(win, text="CALCULAR", command=calcular).pack(pady=10)
        btn_f = ctk.CTkButton(win, text="COBRAR Y TICKET", state="disabled", fg_color="#f1c40f", text_color="black")
        btn_f.pack(pady=10)

    def finalizar_salida(self, id_r, tot, placa, tipo, ent, hrs, win):
        ahora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = conectar(); cursor = conn.cursor()
        cursor.execute("UPDATE ingresos SET salida=?, valor_pagado=?, estado='FINALIZADO' WHERE id=?", (ahora, tot, id_r))
        conn.commit(); conn.close()
        self.imprimir_ticket(placa, tipo, ent, ahora, hrs, tot)
        win.destroy(); self.refrescar_datos()
        messagebox.showinfo("Éxito", "Salida registrada y ticket generado.")

    def imprimir_ticket(self, placa, tipo, ent, sal, hrs, tot):
        ruta = os.path.join("/datos/proyectos/python/parqueadero", f"ticket_{placa}.txt")
        contenido = f"""
        ================================
                CIUDAD BURGOS
        ================================
        FECHA: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        PLACA: {placa} | TIPO: {tipo}
        --------------------------------
        ENTRADA: {ent}
        SALIDA:  {sal}
        TIEMPO:  {hrs} Hora(s)
        --------------------------------
        TOTAL: ${tot:,.0f}
        ================================
        """
        with open(ruta, "w") as f: f.write(contenido)

    def abrir_ventana_reportes(self):
        win = ctk.CTkToplevel(self); win.geometry("600x400")
        tbs = ctk.CTkTabview(win); tbs.pack(fill="both", expand=True)
        tbs.add("Ventas")
        conn = conectar(); cursor = conn.cursor()
        hoy = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT SUM(valor_pagado) FROM ingresos WHERE salida LIKE ?", (f'{hoy}%',))
        ctk.CTkLabel(tbs.tab("Ventas"), text=f"VENTAS HOY: ${cursor.fetchone()[0] or 0:,.0f}", font=("Roboto", 24, "bold")).pack(pady=100)
        conn.close()

    def abrir_ventana_config(self):
        win = ctk.CTkToplevel(self); win.geometry("450x550")
        ctk.CTkLabel(win, text="PRECIOS Y CUPOS", font=("Roboto", 18, "bold")).pack(pady=20)
        tipo = ctk.CTkComboBox(win, values=["Moto Hora", "Moto Mes", "Carro", "Carro Mes", "Camion", "Autobus"], width=250); tipo.pack(pady=10)
        val = ctk.CTkEntry(win, placeholder_text="Precio Tarifa", width=250); val.pack(pady=10)
        cupo = ctk.CTkEntry(win, placeholder_text="Cupo Máximo", width=250); cupo.pack(pady=10)
        
        def actualizar():
            if not val.get() or not cupo.get(): return
            conn = conectar(); cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO configuracion (tipo_vehiculo, tarifa_hora, cupos_totales) VALUES (?,?,?)", (tipo.get(), val.get(), cupo.get()))
            conn.commit(); conn.close(); win.destroy(); self.refrescar_datos()
        ctk.CTkButton(win, text="GUARDAR", command=actualizar).pack(pady=20)

    def refrescar_datos(self):
        try:
            conn = conectar(); cursor = conn.cursor()
            cursor.execute("SELECT tipo_vehiculo, cupos_totales FROM configuracion")
            conf = dict(cursor.fetchall())
            cursor.execute("SELECT tipo, COUNT(*) FROM ingresos WHERE estado='EN SITIO' GROUP BY tipo")
            ocu = dict(cursor.fetchall())
            
            self.card_m_hora.configure(text=f"{ocu.get('Moto Hora', 0)} / {conf.get('Moto Hora', 20)}")
            self.card_m_mes.configure(text=f"{ocu.get('Moto Mes', 0)} / {conf.get('Moto Mes', 15)}")
            
            for i in self.tabla_s.get_children(): self.tabla_s.delete(i)
            cursor.execute("SELECT placa, marca, tipo, propietario, entrada FROM ingresos WHERE estado='EN SITIO'")
            for r in cursor.fetchall(): self.tabla_s.insert("", "end", values=r)

            for i in self.tabla_m.get_children(): self.tabla_m.delete(i)
            cursor.execute("SELECT placa, marca, propietario, telefono, fecha_vencimiento, tipo FROM mensualidades")
            al = 0
            for r in cursor.fetchall():
                v = datetime.strptime(r[4], '%Y-%m-%d %H:%M:%S')
                tag = ""
                if v < datetime.now(): tag = "vencido"; al += 1
                elif v <= (datetime.now() + timedelta(days=3)): tag = "por_vencer"; al += 1
                self.tabla_m.insert("", "end", values=r, tags=(tag,))
            self.card_vencidos.configure(text=str(al))
            conn.close()
        except: pass
        self.after(5000, self.refrescar_datos)

if __name__ == "__main__":
    app = DashboardBurgos()
    app.mainloop()