from dataclasses import dataclass

import pandas as pd

TOLERANCIA_DIAS = 3

COLUMNAS_PAR = [
    "regla",
    "fecha_banco", "operacion_banco", "descripcion", "monto_banco",
    "fecha_libro", "comprobante", "glosa", "operacion_libro", "monto_libro",
    "id_banco", "id_libro",
]


@dataclass
class Resultado:
    conciliados: pd.DataFrame
    diferencias_monto: pd.DataFrame
    duplicados: pd.DataFrame
    solo_banco: pd.DataFrame
    solo_registro: pd.DataFrame


def centimos(monto):
    return (monto * 100).round().astype("int64")


def separar_duplicados(libro):
    repetido = libro.duplicated(subset=["operacion", "monto"], keep="first") & libro["operacion"].notna()
    return libro[~repetido], libro[repetido]


def preparar(banco, libro):
    b = banco.reset_index(names="id_banco").rename(
        columns={"fecha": "fecha_banco", "operacion": "operacion_banco", "monto": "monto_banco"})
    l = libro.reset_index(names="id_libro").rename(
        columns={"fecha": "fecha_libro", "operacion": "operacion_libro", "monto": "monto_libro"})
    return b, l


def cruzar_por_operacion(b, l):
    candidatos = l[l["operacion_libro"].notna()].drop_duplicates("operacion_libro")
    pares = b.merge(candidatos, left_on="operacion_banco", right_on="operacion_libro")
    cuadran = (pares["monto_banco"] - pares["monto_libro"]).abs() < 0.005
    conciliados = pares[cuadran].assign(regla="operacion")
    diferencias = pares[~cuadran].assign(regla="operacion")
    diferencias["diferencia"] = (diferencias["monto_banco"] - diferencias["monto_libro"]).round(2)
    return conciliados, diferencias


def cruzar_por_monto_y_fecha(b, l, tolerancia_dias):
    pares = b.assign(centimos=centimos(b["monto_banco"])).merge(
        l.assign(centimos=centimos(l["monto_libro"])), on="centimos")
    pares["dias"] = (pares["fecha_libro"] - pares["fecha_banco"]).dt.days.abs()
    pares = pares[pares["dias"] <= tolerancia_dias].sort_values(["dias", "id_banco", "id_libro"])

    usados_banco, usados_libro, elegidos = set(), set(), []
    for fila in pares.itertuples():
        if fila.id_banco not in usados_banco and fila.id_libro not in usados_libro:
            usados_banco.add(fila.id_banco)
            usados_libro.add(fila.id_libro)
            elegidos.append(fila.Index)
    return pares.loc[elegidos].assign(regla="monto_fecha")


def conciliar(banco, libro, tolerancia_dias=TOLERANCIA_DIAS):
    libro_unico, duplicados = separar_duplicados(libro)
    b, l = preparar(banco, libro_unico)

    por_operacion, diferencias = cruzar_por_operacion(b, l)
    cruzados_banco = set(por_operacion["id_banco"]) | set(diferencias["id_banco"])
    cruzados_libro = set(por_operacion["id_libro"]) | set(diferencias["id_libro"])

    resto_b = b[~b["id_banco"].isin(cruzados_banco)]
    resto_l = l[~l["id_libro"].isin(cruzados_libro)]
    por_monto = cruzar_por_monto_y_fecha(resto_b, resto_l, tolerancia_dias)

    conciliados = pd.concat([por_operacion, por_monto], ignore_index=True)
    conciliados = conciliados[COLUMNAS_PAR].sort_values(["fecha_banco", "id_banco"], ignore_index=True)
    sin_banco = resto_b.loc[~resto_b["id_banco"].isin(por_monto["id_banco"]), "id_banco"]
    sin_libro = resto_l.loc[~resto_l["id_libro"].isin(por_monto["id_libro"]), "id_libro"]

    return Resultado(
        conciliados=conciliados,
        diferencias_monto=diferencias[COLUMNAS_PAR + ["diferencia"]].reset_index(drop=True),
        duplicados=duplicados.reset_index(drop=True),
        solo_banco=banco.loc[sin_banco].reset_index(drop=True),
        solo_registro=libro.loc[sin_libro].reset_index(drop=True),
    )


def cuadre(resultado, banco, libro, saldo_inicial, saldo_inicial_libros=None):
    if saldo_inicial_libros is None:
        saldo_inicial_libros = saldo_inicial
    saldo_banco = round(saldo_inicial + banco["monto"].sum(), 2)
    saldo_libros = round(saldo_inicial_libros + libro["monto"].sum(), 2)
    banco_ajustado = round(saldo_banco + resultado.solo_registro["monto"].sum(), 2)
    libros_ajustado = round(
        saldo_libros
        + resultado.solo_banco["monto"].sum()
        + resultado.diferencias_monto["diferencia"].sum()
        - resultado.duplicados["monto"].sum(),
        2,
    )
    return {
        "saldo_banco": saldo_banco,
        "saldo_libros": saldo_libros,
        "banco_ajustado": banco_ajustado,
        "libros_ajustado": libros_ajustado,
        "diferencia": round(banco_ajustado - libros_ajustado, 2),
    }


def main():
    from pathlib import Path

    from lectura import leer_extracto, leer_libro

    data = Path(__file__).resolve().parent.parent / "data"
    banco, saldo_inicial = leer_extracto(data / "extracto_banco.csv")
    libro = leer_libro(data / "libro_bancos.xlsx")
    resultado = conciliar(banco, libro)
    saldos = cuadre(resultado, banco, libro, saldo_inicial)

    reglas = resultado.conciliados["regla"].value_counts()
    print(f"Conciliados:          {len(resultado.conciliados):>3}  "
          f"({reglas.get('operacion', 0)} por número de operación, {reglas.get('monto_fecha', 0)} por monto y fecha)")
    print(f"Diferencias de monto: {len(resultado.diferencias_monto):>3}")
    print(f"Duplicados:           {len(resultado.duplicados):>3}")
    print(f"Solo en el banco:     {len(resultado.solo_banco):>3}")
    print(f"Solo en el registro:  {len(resultado.solo_registro):>3}")
    print()
    print(f"Saldo según banco:    {saldos['saldo_banco']:>12,.2f}")
    print(f"Saldo según libros:   {saldos['saldo_libros']:>12,.2f}")
    print(f"Banco ajustado:       {saldos['banco_ajustado']:>12,.2f}")
    print(f"Libros ajustado:      {saldos['libros_ajustado']:>12,.2f}")
    print(f"Diferencia:           {saldos['diferencia']:>12,.2f}")


if __name__ == "__main__":
    main()
