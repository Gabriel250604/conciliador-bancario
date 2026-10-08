import io
import re
import unicodedata
from pathlib import Path

import pandas as pd

COLUMNAS_EXTRACTO = {"fecha", "descripcion", "n_operacion", "cargo", "abono", "saldo"}
COLUMNAS_LIBRO = {"fecha", "comprobante", "glosa", "n_operacion", "debe", "haber"}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", texto.lower()).strip("_")


def leer_texto(ruta):
    datos = Path(ruta).read_bytes()
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        return datos.decode("cp1252")


def verificar_columnas(tabla, requeridas, archivo):
    faltantes = requeridas - set(tabla.columns)
    if faltantes:
        raise ValueError(f"Al {archivo} le faltan columnas: {', '.join(sorted(faltantes))}")


def montos(columna, nombre):
    limpio = columna.astype("string").str.replace(",", "", regex=False).str.strip().fillna("")
    valores = pd.to_numeric(limpio.mask(limpio == "", "0"), errors="coerce")
    if valores.isna().any():
        fila = valores.isna().idxmax()
        raise ValueError(f"Monto no válido en la columna {nombre}, fila {fila + 1}: '{columna[fila]}'")
    return valores.astype("float64")


def verificar_saldos(movimientos, saldo_inicial):
    calculado = (saldo_inicial + movimientos["monto"].cumsum()).round(2)
    descuadre = (calculado - movimientos["saldo"]).abs() > 0.005
    if descuadre.any():
        fila = descuadre.idxmax()
        raise ValueError(
            f"El saldo del extracto no cuadra en el movimiento {fila + 1} "
            f"(operación {movimientos.at[fila, 'operacion']}): se esperaba "
            f"{calculado[fila]:,.2f} y figura {movimientos.at[fila, 'saldo']:,.2f}"
        )


def leer_extracto(ruta):
    lineas = leer_texto(ruta).splitlines()
    inicio = next((i for i, linea in enumerate(lineas) if normalizar(linea.split(";")[0]) == "fecha"), None)
    if inicio is None:
        raise ValueError("No se encontró la fila de encabezados del extracto")

    saldo_inicial = None
    for linea in lineas[:inicio]:
        campos = linea.split(";")
        if normalizar(campos[0]) == "saldo_inicial":
            saldo_inicial = float(campos[1].replace(",", ""))

    tabla = pd.read_csv(io.StringIO("\n".join(lineas[inicio:])), sep=";", dtype=str, keep_default_na=False)
    tabla.columns = [normalizar(c) for c in tabla.columns]
    verificar_columnas(tabla, COLUMNAS_EXTRACTO, "extracto")
    tabla = tabla[tabla["fecha"].str.strip() != ""].reset_index(drop=True)

    movimientos = pd.DataFrame({
        "fecha": pd.to_datetime(tabla["fecha"].str.strip(), format="%d/%m/%Y"),
        "descripcion": tabla["descripcion"].astype("string").str.strip(),
        "operacion": tabla["n_operacion"].astype("string").str.strip().str.zfill(8),
        "monto": (montos(tabla["abono"], "Abono") - montos(tabla["cargo"], "Cargo")).round(2),
        "saldo": montos(tabla["saldo"], "Saldo"),
    })
    if saldo_inicial is not None:
        verificar_saldos(movimientos, saldo_inicial)
    return movimientos, saldo_inicial


def leer_libro(ruta, hoja=0):
    tabla = pd.read_excel(ruta, sheet_name=hoja)
    tabla.columns = [normalizar(c) for c in tabla.columns]
    verificar_columnas(tabla, COLUMNAS_LIBRO, "libro bancos")
    tabla = tabla.dropna(how="all").reset_index(drop=True)

    debe = pd.to_numeric(tabla["debe"], errors="coerce").fillna(0)
    haber = pd.to_numeric(tabla["haber"], errors="coerce").fillna(0)
    invalidos = ((debe > 0) & (haber > 0)) | ((debe == 0) & (haber == 0))
    if invalidos.any():
        fila = invalidos.idxmax()
        raise ValueError(
            f"El asiento {tabla.at[fila, 'comprobante']} debe tener monto solo en Debe o solo en Haber"
        )

    operacion = pd.to_numeric(tabla["n_operacion"], errors="coerce").astype("Int64")
    return pd.DataFrame({
        "fecha": pd.to_datetime(tabla["fecha"]),
        "comprobante": tabla["comprobante"].astype("string").str.strip(),
        "glosa": tabla["glosa"].astype("string").str.strip(),
        "operacion": operacion.astype("string").str.zfill(8),
        "monto": (debe - haber).round(2),
    })
