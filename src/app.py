import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from reporte import generar_reporte

VERDE = "#1E7B34"
ROJO = "#B00020"


class Aplicacion(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Conciliador bancario")
        self.resizable(False, False)
        self.extracto = tk.StringVar()
        self.libro = tk.StringVar()
        self.salida = tk.StringVar()
        self.reporte = None
        self.construir()

    def construir(self):
        marco = ttk.Frame(self, padding=16)
        marco.grid(sticky="nsew")

        self.campo(marco, 0, "Extracto bancario (.csv)", self.extracto, self.elegir_extracto)
        self.campo(marco, 1, "Libro bancos (.xlsx)", self.libro, self.elegir_libro)
        self.campo(marco, 2, "Guardar reporte en", self.salida, self.elegir_salida)

        ttk.Button(marco, text="Conciliar", command=self.conciliar).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(12, 8))

        self.resumen = ttk.Label(marco, text="", justify="left", font=("Consolas", 10))
        self.resumen.grid(row=4, column=0, columnspan=3, sticky="w")
        self.estado = ttk.Label(marco, text="", font=("Segoe UI", 10, "bold"))
        self.estado.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self.boton_abrir = ttk.Button(marco, text="Abrir reporte", command=self.abrir_reporte, state="disabled")
        self.boton_abrir.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(12, 0))

    def campo(self, marco, fila, etiqueta, variable, comando):
        ttk.Label(marco, text=etiqueta).grid(row=fila, column=0, sticky="w", pady=4)
        ttk.Entry(marco, textvariable=variable, width=55).grid(row=fila, column=1, padx=8, pady=4)
        ttk.Button(marco, text="Elegir...", command=comando).grid(row=fila, column=2, pady=4)

    def elegir_extracto(self):
        ruta = filedialog.askopenfilename(
            title="Elegir extracto bancario", filetypes=[("Archivos CSV", "*.csv"), ("Todos", "*.*")])
        if ruta:
            self.extracto.set(ruta)
            if not self.salida.get():
                self.salida.set(str(Path(ruta).with_name("conciliacion.xlsx")))

    def elegir_libro(self):
        ruta = filedialog.askopenfilename(
            title="Elegir libro bancos", filetypes=[("Libros de Excel", "*.xlsx"), ("Todos", "*.*")])
        if ruta:
            self.libro.set(ruta)

    def elegir_salida(self):
        ruta = filedialog.asksaveasfilename(
            title="Guardar reporte", defaultextension=".xlsx", initialfile="conciliacion.xlsx",
            filetypes=[("Libros de Excel", "*.xlsx")])
        if ruta:
            self.salida.set(ruta)

    def conciliar(self):
        faltantes = [nombre for nombre, variable in (
            ("el extracto bancario", self.extracto),
            ("el libro bancos", self.libro),
            ("dónde guardar el reporte", self.salida),
        ) if not variable.get().strip()]
        if faltantes:
            messagebox.showwarning("Faltan datos", "Falta elegir " + ", ".join(faltantes) + ".")
            return

        self.config(cursor="watch")
        self.update_idletasks()
        try:
            resultado, saldos = generar_reporte(self.extracto.get(), self.libro.get(), self.salida.get())
        except PermissionError:
            messagebox.showerror(
                "No se pudo guardar", "El reporte está abierto en Excel. Ciérralo y vuelve a intentarlo.")
            return
        except (FileNotFoundError, ValueError) as error:
            messagebox.showerror("No se pudo conciliar", str(error))
            return
        except Exception as error:
            messagebox.showerror("Error inesperado", f"{type(error).__name__}: {error}")
            return
        finally:
            self.config(cursor="")

        self.reporte = Path(self.salida.get())
        self.resumen.config(text="\n".join([
            f"Conciliados:           {len(resultado.conciliados):>4}",
            f"Solo en el banco:      {len(resultado.solo_banco):>4}",
            f"Solo en el registro:   {len(resultado.solo_registro):>4}",
            f"Diferencias de monto:  {len(resultado.diferencias_monto):>4}",
            f"Duplicados:            {len(resultado.duplicados):>4}",
        ]))
        if saldos["diferencia"] == 0:
            self.estado.config(text="La conciliación cuadra. Diferencia final: 0.00", foreground=VERDE)
        else:
            self.estado.config(text=f"Diferencia sin explicar: {saldos['diferencia']:,.2f}", foreground=ROJO)
        self.boton_abrir.config(state="normal")

    def abrir_reporte(self):
        if sys.platform == "win32":
            os.startfile(self.reporte)
        elif sys.platform == "darwin":
            subprocess.run(["open", self.reporte], check=False)
        else:
            subprocess.run(["xdg-open", self.reporte], check=False)


if __name__ == "__main__":
    Aplicacion().mainloop()
