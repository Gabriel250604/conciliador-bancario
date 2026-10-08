import argparse
import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

INICIO = date(2026, 9, 1)
FIN = date(2026, 9, 30)
SALDO_INICIAL = 120000.00

CLIENTES = [
    "Comercial Santa Rosa SAC",
    "Distribuidora El Trébol EIRL",
    "Inversiones Huaral SAC",
    "Ferretería San Martín EIRL",
    "Agroindustrias del Norte SAC",
    "Textiles Carabayllo SAC",
    "Servicios Generales Ancón EIRL",
    "Importaciones Pacífico SAC",
]

PROVEEDORES = [
    "Transportes Rímac SAC",
    "Suministros Industriales Lima EIRL",
    "Papelera Los Andes SAC",
    "Mantenimiento Integral Perú SAC",
    "Tecnología y Redes Callao EIRL",
    "Seguridad Vigilancia Total SAC",
]

CANTIDADES = {
    "normales": 110,
    "sin_operacion": 15,
    "desfase_fecha": 30,
    "diferencias_monto": 3,
    "duplicados": 2,
    "comisiones": 5,
    "itf": 3,
    "intereses": 1,
    "cheques_en_transito": 3,
    "depositos_en_transito": 2,
}


class Generador:
    def __init__(self, semilla):
        self.rng = random.Random(semilla)
        self.operaciones = set()
        self.montos = set()
        self.banco = []
        self.registro = []
        self.esperadas = []

    def fecha(self, desde=INICIO, hasta=FIN):
        while True:
            dia = desde + timedelta(days=self.rng.randint(0, (hasta - desde).days))
            if dia.weekday() < 6:
                return dia

    def operacion(self):
        while True:
            numero = f"{self.rng.randint(0, 99_999_999):08d}"
            if numero not in self.operaciones:
                self.operaciones.add(numero)
                return numero

    def monto(self, minimo, maximo):
        while True:
            valor = round(self.rng.uniform(minimo, maximo), 2)
            if valor not in self.montos:
                self.montos.add(valor)
                return valor

    def factura(self):
        return f"F001-{self.rng.randint(1, 9999):06d}"

    def movimiento(self, ingreso):
        if ingreso:
            cliente = self.rng.choice(CLIENTES)
            if self.rng.random() < 0.3:
                descripcion = "DEPÓSITO EN EFECTIVO"
            else:
                descripcion = f"TRANSF. DE {cliente.upper()}"
            glosa = f"Cobranza {self.factura()} {cliente}"
        else:
            proveedor = self.rng.choice(PROVEEDORES)
            descripcion = f"TRANSF. A {proveedor.upper()}"
            glosa = f"Pago {self.factura()} {proveedor}"
        return descripcion, glosa

    def agregar_banco(self, fecha, descripcion, operacion, monto, ingreso):
        self.banco.append({
            "fecha": fecha,
            "descripcion": descripcion,
            "operacion": operacion,
            "cargo": 0.0 if ingreso else monto,
            "abono": monto if ingreso else 0.0,
        })

    def agregar_registro(self, fecha, glosa, operacion, monto, ingreso):
        fila = {
            "id": len(self.registro),
            "fecha": fecha,
            "glosa": glosa,
            "operacion": operacion,
            "debe": monto if ingreso else 0.0,
            "haber": 0.0 if ingreso else monto,
        }
        self.registro.append(fila)
        return fila

    def esperar(self, tipo, operacion=None, registro=None, monto_banco=None, monto_registro=None):
        self.esperadas.append({
            "tipo": tipo,
            "operacion": operacion,
            "registro_id": registro,
            "monto_banco": monto_banco,
            "monto_registro": monto_registro,
        })

    def normales(self):
        total = CANTIDADES["normales"]
        sin_operacion = set(self.rng.sample(range(total), CANTIDADES["sin_operacion"]))
        con_desfase = set(self.rng.sample(range(total), CANTIDADES["desfase_fecha"]))
        filas = []
        for i in range(total):
            ingreso = self.rng.random() < 0.5
            fecha = self.fecha(hasta=FIN - timedelta(days=3))
            operacion = self.operacion()
            monto = self.monto(150, 25000)
            descripcion, glosa = self.movimiento(ingreso)
            self.agregar_banco(fecha, descripcion, operacion, monto, ingreso)
            fecha_registro = fecha + timedelta(days=self.rng.randint(1, 2)) if i in con_desfase else fecha
            operacion_registro = None if i in sin_operacion else operacion
            filas.append(self.agregar_registro(fecha_registro, glosa, operacion_registro, monto, ingreso))
        return filas

    def duplicados(self, filas):
        candidatas = [f for f in filas if f["operacion"] is not None]
        for original in self.rng.sample(candidatas, CANTIDADES["duplicados"]):
            ingreso = original["debe"] > 0
            monto = original["debe"] or original["haber"]
            copia = self.agregar_registro(original["fecha"], original["glosa"], original["operacion"], monto, ingreso)
            self.esperar("duplicado", original["operacion"], copia["id"], monto_registro=monto)

    def diferencias_monto(self):
        for _ in range(CANTIDADES["diferencias_monto"]):
            ingreso = self.rng.random() < 0.5
            fecha = self.fecha(hasta=FIN - timedelta(days=3))
            operacion = self.operacion()
            monto = self.monto(1000, 9999)
            entero, centimos = f"{monto:.2f}".split(".")
            if entero[0] == entero[1]:
                entero = entero[0] + str((int(entero[1]) + 1) % 10) + entero[2:]
            mal_digitado = float(f"{entero[1]}{entero[0]}{entero[2:]}.{centimos}")
            self.montos.add(mal_digitado)
            descripcion, glosa = self.movimiento(ingreso)
            self.agregar_banco(fecha, descripcion, operacion, monto, ingreso)
            fila = self.agregar_registro(fecha, glosa, operacion, mal_digitado, ingreso)
            self.esperar("diferencia_monto", operacion, fila["id"], monto, mal_digitado)

    def solo_banco(self):
        for _ in range(CANTIDADES["comisiones"] - 1):
            operacion = self.operacion()
            monto = self.monto(5, 9.5)
            self.agregar_banco(self.fecha(), "COMISIÓN TRANSF. INTERBANCARIA", operacion, monto, False)
            self.esperar("solo_banco", operacion, monto_banco=monto)
        operacion = self.operacion()
        self.montos.add(25.0)
        self.agregar_banco(FIN, "COMISIÓN MANTENIMIENTO DE CUENTA", operacion, 25.0, False)
        self.esperar("solo_banco", operacion, monto_banco=25.0)
        for _ in range(CANTIDADES["itf"]):
            operacion = self.operacion()
            monto = self.monto(0.1, 1.5)
            self.agregar_banco(self.fecha(), "ITF", operacion, monto, False)
            self.esperar("solo_banco", operacion, monto_banco=monto)
        for _ in range(CANTIDADES["intereses"]):
            operacion = self.operacion()
            monto = self.monto(3, 6)
            self.agregar_banco(FIN, "ABONO DE INTERESES", operacion, monto, True)
            self.esperar("solo_banco", operacion, monto_banco=monto)

    def solo_registro(self):
        for _ in range(CANTIDADES["cheques_en_transito"]):
            proveedor = self.rng.choice(PROVEEDORES)
            cheque = self.rng.randint(1, 999999)
            monto = self.monto(500, 8000)
            fila = self.agregar_registro(self.fecha(desde=FIN - timedelta(days=6)),
                                         f"Cheque N° {cheque:06d} a {proveedor}", None, monto, False)
            self.esperar("solo_registro", registro=fila["id"], monto_registro=monto)
        for _ in range(CANTIDADES["depositos_en_transito"]):
            cliente = self.rng.choice(CLIENTES)
            monto = self.monto(500, 8000)
            fila = self.agregar_registro(self.fecha(desde=FIN - timedelta(days=1)),
                                         f"Depósito en tránsito {cliente}", None, monto, True)
            self.esperar("solo_registro", registro=fila["id"], monto_registro=monto)

    def generar(self):
        filas = self.normales()
        self.duplicados(filas)
        self.diferencias_monto()
        self.solo_banco()
        self.solo_registro()


def importe(valor):
    return f"{valor:,.2f}" if valor else ""


def escribir_extracto(movimientos, ruta):
    df = pd.DataFrame(movimientos).sort_values(["fecha", "operacion"], ignore_index=True)
    df["saldo"] = SALDO_INICIAL + (df["abono"] - df["cargo"]).cumsum()
    lineas = [
        "Estado de cuenta corriente;;;;;",
        "Cuenta;000-1234567-0-01;;;;",
        "Moneda;Soles;;;;",
        f"Periodo;{INICIO:%d/%m/%Y} al {FIN:%d/%m/%Y};;;;",
        f"Saldo inicial;{importe(SALDO_INICIAL)};;;;",
        ";;;;;",
        "Fecha;Descripción;N° Operación;Cargo;Abono;Saldo",
    ]
    for f in df.itertuples():
        lineas.append(f"{f.fecha:%d/%m/%Y};{f.descripcion};{f.operacion};"
                      f"{importe(f.cargo)};{importe(f.abono)};{importe(f.saldo)}")
    ruta.write_text("\n".join(lineas) + "\n", encoding="cp1252", newline="\r\n")
    return df


def escribir_registro(filas, ruta):
    df = pd.DataFrame(filas)
    df["orden"] = df["fecha"].map(lambda d: d.toordinal())
    df = df.sort_values(["orden", "id"], ignore_index=True)
    df["comprobante"] = [f"CB-{n:04d}" for n in range(1, len(df) + 1)]
    df["operacion"] = pd.to_numeric(df["operacion"]).astype("Int64")
    salida = pd.DataFrame({
        "Fecha": pd.to_datetime(df["fecha"]),
        "Comprobante": df["comprobante"],
        "Glosa": df["glosa"],
        "N° Operación": df["operacion"],
        "Debe": df["debe"].where(df["debe"] > 0),
        "Haber": df["haber"].where(df["haber"] > 0),
    })
    salida.to_excel(ruta, sheet_name="Libro Bancos", index=False)
    return dict(zip(df["id"], df["comprobante"]))


def escribir_esperadas(esperadas, comprobantes, ruta):
    df = pd.DataFrame(esperadas)
    df["comprobante"] = df["registro_id"].map(comprobantes)
    df = df[["tipo", "operacion", "comprobante", "monto_banco", "monto_registro"]]
    df.sort_values(["tipo", "operacion", "comprobante"], ignore_index=True).to_csv(ruta, index=False)
    return df


def main():
    parser = argparse.ArgumentParser(description="Genera un extracto bancario y un libro bancos de prueba.")
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--carpeta", type=Path, default=Path("data"))
    args = parser.parse_args()

    args.carpeta.mkdir(parents=True, exist_ok=True)
    generador = Generador(args.semilla)
    generador.generar()

    extracto = escribir_extracto(generador.banco, args.carpeta / "extracto_banco.csv")
    comprobantes = escribir_registro(generador.registro, args.carpeta / "libro_bancos.xlsx")
    esperadas = escribir_esperadas(generador.esperadas, comprobantes, args.carpeta / "diferencias_esperadas.csv")

    print(f"Extracto bancario: {len(extracto)} movimientos")
    print(f"Libro bancos:      {len(generador.registro)} asientos")
    print(f"Saldo final banco: {extracto['saldo'].iloc[-1]:,.2f}")
    print("Diferencias sembradas:")
    for tipo, cantidad in esperadas["tipo"].value_counts().sort_index().items():
        print(f"  {tipo:<17} {cantidad}")


if __name__ == "__main__":
    main()
