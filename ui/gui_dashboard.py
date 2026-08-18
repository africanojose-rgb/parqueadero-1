import sys
import math
from datetime import datetime

import customtkinter as ctk
from tkinter import ttk, messagebox

import services.casos_uso as svc
from domain import enums

TIPOS_HORA = [t.value for t in enums.TIPOS_HORA]
TIPOS_MES = [t.value for t in enums.TIPOS_MENSUALES]
TIPOS_CONFIG = [t.value for t in enums.TipoVehiculo]


def mostrar_error(e: Exception):
    messagebox.showerror("Error", str(e))


class DashboardBurgos(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CIUDAD BURGOS v3.3 - Gestión Total")
        self.geometry("1300x850")

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

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

        self.main_view = ctk.CTkFrame(self, fg_color="transparent")
        self.main_view.grid(row=0, column=1, padx=25, pady=20, sticky="nsew")

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
        btn = ctk.CTkButton(self.sidebar, text=txt, command=cmd, height=45,
                            fg_color="transparent", border_width=1)
        btn.pack(pady=8, padx=20, fill="x")

    def crear_card(self, master, tit, col):
        f = ctk.CTkFrame(master, fg_color=col, corner_radius=12)
        f.pack(side="left", padx=5, expand=True, fill="both")
        lbl = ctk.CTkLabel(f, text="0 / 0", font=("Roboto", 22, "bold"), text_color="white")
        lbl.pack(pady=(15, 5))
        ctk.CTkLabel(f, text=tit, font=("Roboto", 10), text_color="white").pack(pady=(0, 10))
        return lbl

    def setup_tablas(self):
        self.tabla_m = ttk.Treeview(self.tabs_info.tab("Mensualidades"),
                                     columns=("P", "M", "D", "T", "V", "E"), show="headings")
        for c, h in zip(("P", "M", "D", "T", "V", "E"),
                        ("PLACA", "MARCA", "DUEÑO", "TELÉFONO", "VENCE", "TIPO")):
            self.tabla_m.heading(c, text=h)
            self.tabla_m.column(c, anchor="center")
        self.tabla_m.tag_configure("vencido", background="#721c24", foreground="white")
        self.tabla_m.tag_configure("por_vencer", background="#856404", foreground="white")
        self.tabla_m.pack(fill="both", expand=True)

        btn_m_frame = ctk.CTkFrame(self.tabs_info.tab("Mensualidades"), fg_color="transparent")
        btn_m_frame.pack(pady=10)
        ctk.CTkButton(btn_m_frame, text="🔄 RENOVAR MES", fg_color="#27ae60",
                      command=self.proceso_renovacion).pack(side="left", padx=10)
        ctk.CTkButton(btn_m_frame, text="🗑️ DAR DE BAJA", fg_color="#e74c3c",
                      command=self.eliminar_mensualidad).pack(side="left", padx=10)

        self.tabla_s = ttk.Treeview(self.tabs_info.tab("Vehículos en Sitio"),
                                    columns=("P", "M", "T", "D", "E"), show="headings")
        for c, h in zip(("P", "M", "T", "D", "E"),
                        ("PLACA", "MARCA", "TIPO", "DUEÑO", "ENTRADA")):
            self.tabla_s.heading(c, text=h)
            self.tabla_s.column(c, anchor="center")
        self.tabla_s.pack(fill="both", expand=True)

    def buscar_placa(self):
        placa = self.entry_busqueda.get().strip().upper()
        if not placa:
            return
        ingreso = svc.buscar_placa(placa)
        if ingreso:
            messagebox.showinfo("Resultado",
                                f"PLACA: {ingreso.placa}\nMARCA: {ingreso.marca}\n"
                                f"TIPO: {ingreso.tipo}\nESTADO: {ingreso.estado.value}")
        else:
            messagebox.showwarning("Buscador", "No hay registros de esa placa en sitio.")

    def abrir_ventana_ingreso(self):
        win = ctk.CTkToplevel(self)
        win.geometry("400x600")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="ENTRADA HORA", font=("Roboto", 18, "bold")).pack(pady=20)
        p = ctk.CTkEntry(win, placeholder_text="PLACA", width=250)
        m = ctk.CTkEntry(win, placeholder_text="MARCA", width=250)
        d = ctk.CTkEntry(win, placeholder_text="DUEÑO", width=250)
        t = ctk.CTkEntry(win, placeholder_text="TELÉFONO", width=250)
        v = ctk.CTkComboBox(win, values=TIPOS_HORA, width=250)
        for widget in (p, m, d, t, v):
            widget.pack(pady=10)

        def guardar():
            try:
                svc.registrar_entrada(p.get(), v.get(), m.get(), d.get(), t.get())
                win.destroy()
                self.refrescar_datos()
            except Exception as e:
                mostrar_error(e)
        ctk.CTkButton(win, text="REGISTRAR ENTRADA", fg_color="#2ecc71",
                      command=guardar).pack(pady=20)

    def abrir_ventana_mensualidad(self):
        win = ctk.CTkToplevel(self)
        win.geometry("400x650")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="NUEVO PAGO MENSUAL", font=("Roboto", 18, "bold")).pack(pady=20)
        p = ctk.CTkEntry(win, placeholder_text="PLACA", width=250)
        m = ctk.CTkEntry(win, placeholder_text="MARCA", width=250)
        d = ctk.CTkEntry(win, placeholder_text="PROPIETARIO", width=250)
        t = ctk.CTkEntry(win, placeholder_text="TELÉFONO", width=250)
        v = ctk.CTkComboBox(win, values=TIPOS_MES, width=250)
        for widget in (p, m, d, t, v):
            widget.pack(pady=10)

        def guardar_mes():
            try:
                res = svc.registrar_mensualidad(p.get(), m.get(), d.get(), t.get(), v.get())
                messagebox.showinfo("Éxito",
                                    f"Mensualidad activada para {res['placa']}\n"
                                    f"Vence: {res['vencimiento']}")
                win.destroy()
                self.refrescar_datos()
            except Exception as e:
                mostrar_error(e)
        ctk.CTkButton(win, text="COBRAR Y ACTIVAR", fg_color="#9b59b6",
                      command=guardar_mes).pack(pady=20)

    def proceso_renovacion(self):
        selected = self.tabla_m.focus()
        if not selected:
            return messagebox.showwarning("Atención", "Seleccione un cliente.")
        vals = self.tabla_m.item(selected, "values")
        if not messagebox.askyesno("Confirmar", f"¿Renovar placa {vals[0]}?"):
            return
        try:
            svc.renovar_mensualidad(vals[0])
            self.refrescar_datos()
            messagebox.showinfo("OK", "Renovación exitosa y registrada en caja.")
        except Exception as e:
            mostrar_error(e)

    def eliminar_mensualidad(self):
        selected = self.tabla_m.focus()
        if not selected:
            return messagebox.showwarning("Atención", "Seleccione un registro.")
        placa = self.tabla_m.item(selected, "values")[0]
        if messagebox.askyesno("Baja", f"¿Eliminar mensualidad de {placa}?"):
            try:
                svc.eliminar_mensualidad(placa)
                self.refrescar_datos()
            except Exception as e:
                mostrar_error(e)

    def abrir_ventana_cierre(self):
        win = ctk.CTkToplevel(self)
        win.geometry("500x650")
        ctk.CTkLabel(win, text="CORTE DE CAJA DETALLADO", font=("Roboto", 20, "bold")).pack(pady=20)
        try:
            r = svc.obtener_resumen_cierre()
        except Exception as e:
            return mostrar_error(e)
        info = (
            f"FECHA: {r['fecha']}\n\n"
            f"HORAS: {r['horas_count']} vehículos | ${r['horas_total']:,.0f}\n"
            f"MESES: {r['mes_count']} pagos | ${r['mes_total']:,.0f}\n\n"
            f"TOTAL GENERAL: ${r['total']:,.0f}"
        )
        ctk.CTkLabel(win, text=info, font=("Courier", 18), justify="left").pack(pady=30)

        def confirmar():
            try:
                svc.confirmar_cierre()
                win.destroy()
                messagebox.showinfo("Cierre", "Caja cerrada correctamente.")
            except Exception as e:
                mostrar_error(e)
        ctk.CTkButton(win, text="CONFIRMAR CIERRE", fg_color="#e74c3c",
                      command=confirmar).pack(pady=20)

    def abrir_ventana_salida(self):
        win = ctk.CTkToplevel(self)
        win.geometry("400x500")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="COBRAR SALIDA", font=("Roboto", 18, "bold")).pack(pady=20)
        ent_p = ctk.CTkEntry(win, placeholder_text="PLACA", width=250)
        ent_p.pack(pady=10)
        lbl = ctk.CTkLabel(win, text="...")
        lbl.pack(pady=10)

        cobro = {}

        def calcular():
            try:
                cobro.clear()
                cobro.update(svc.previsualizar_cobro(ent_p.get()))
                lbl.configure(text=f"MARCA: {cobro['marca']}\nHORAS: {cobro['horas']}\n"
                                   f"TOTAL: ${cobro['total']:,.0f}")
                btn_f.configure(state="normal")
            except Exception as e:
                lbl.configure(text="❌ " + str(e))
                btn_f.configure(state="disabled")

        def cobrar():
            try:
                res = svc.cobrar_salida(ent_p.get())
                win.destroy()
                self.refrescar_datos()
                messagebox.showinfo("Éxito",
                                    f"Salida registrada. Ticket: {res['ticket']}")
            except Exception as e:
                mostrar_error(e)

        ctk.CTkButton(win, text="CALCULAR", command=calcular).pack(pady=10)
        btn_f = ctk.CTkButton(win, text="COBRAR Y TICKET", state="disabled",
                              fg_color="#f1c40f", text_color="black", command=cobrar)
        btn_f.pack(pady=10)

    def abrir_ventana_reportes(self):
        win = ctk.CTkToplevel(self)
        win.geometry("600x400")
        tbs = ctk.CTkTabview(win)
        tbs.pack(fill="both", expand=True)
        tbs.add("Ventas")
        try:
            total = svc.ventas_hoy()
        except Exception as e:
            return mostrar_error(e)
        ctk.CTkLabel(tbs.tab("Ventas"),
                     text=f"VENTAS HOY: ${total:,.0f}",
                     font=("Roboto", 24, "bold")).pack(pady=100)

    def abrir_ventana_config(self):
        win = ctk.CTkToplevel(self)
        win.geometry("450x600")
        ctk.CTkLabel(win, text="PRECIOS Y CUPOS", font=("Roboto", 18, "bold")).pack(pady=20)
        tipo = ctk.CTkComboBox(win, values=TIPOS_CONFIG, width=250)
        tipo.pack(pady=10)
        val = ctk.CTkEntry(win, placeholder_text="Tarifa Hora", width=250)
        val.pack(pady=10)
        val_mes = ctk.CTkEntry(win, placeholder_text="Tarifa Mes", width=250)
        val_mes.pack(pady=10)
        cupo = ctk.CTkEntry(win, placeholder_text="Cupo Máximo", width=250)
        cupo.pack(pady=10)

        def actualizar():
            try:
                svc.guardar_configuracion(tipo.get(), val.get(), val_mes.get(), cupo.get())
                win.destroy()
                self.refrescar_datos()
            except Exception as e:
                mostrar_error(e)
        ctk.CTkButton(win, text="GUARDAR", command=actualizar).pack(pady=20)

    def refrescar_datos(self):
        try:
            ocu = svc.calcular_ocupacion()
            self.card_m_hora.configure(text=f"{ocu['moto_hora'][0]} / {ocu['moto_hora'][1]}")
            self.card_m_mes.configure(text=f"{ocu['moto_mes'][0]} / {ocu['moto_mes'][1]}")
            self.card_otros.configure(text=f"{ocu['otros'][0]} / {ocu['otros'][1]}")
            self.card_vencidos.configure(text=str(ocu['alertas_mes']))

            for i in self.tabla_s.get_children():
                self.tabla_s.delete(i)
            for r in svc.listar_en_sitio():
                self.tabla_s.insert("", "end",
                                    values=(r["placa"], r["marca"], r["tipo"],
                                            r["propietario"], r["entrada"]))

            for i in self.tabla_m.get_children():
                self.tabla_m.delete(i)
            for r in svc.listar_mensualidades():
                self.tabla_m.insert("", "end",
                                    values=(r["placa"], r["marca"], r["propietario"],
                                            r["telefono"], r["vencimiento"], r["tipo"]),
                                    tags=(r["tag"],))
        except Exception as e:
            print(f"[refrescar_datos] error: {e}")
        self.after(5000, self.refrescar_datos)


if __name__ == "__main__":
    app = DashboardBurgos()
    app.mainloop()
