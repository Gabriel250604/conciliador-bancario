from pathlib import Path

import pandas as pd
import pytest

from conciliacion import conciliar, cuadre
from lectura import leer_extracto, leer_libro

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def datos():
    banco, saldo_inicial = leer_extracto(DATA / "extracto_banco.csv")
    libro = leer_libro(DATA / "libro_bancos.xlsx")
    return banco, libro, saldo_inicial, conciliar(banco, libro)


@pytest.fixture(scope="module")
def esperadas():
    return pd.read_csv(DATA / "diferencias_esperadas.csv", dtype={"operacion": str, "comprobante": str})


def claves(esperadas, tipo, columna):
    return set(esperadas.loc[esperadas["tipo"] == tipo, columna])


def test_concilia_los_110_movimientos_normales(datos):
    *_, resultado = datos
    assert len(resultado.conciliados) == 110


def test_los_asientos_sin_operacion_concilian_por_monto_y_fecha(datos):
    *_, resultado = datos
    assert (resultado.conciliados["regla"] == "monto_fecha").sum() == 15


def test_encuentra_lo_que_solo_esta_en_el_banco(datos, esperadas):
    *_, resultado = datos
    assert set(resultado.solo_banco["operacion"]) == claves(esperadas, "solo_banco", "operacion")


def test_encuentra_lo_que_solo_esta_en_el_registro(datos, esperadas):
    *_, resultado = datos
    assert set(resultado.solo_registro["comprobante"]) == claves(esperadas, "solo_registro", "comprobante")


def test_encuentra_las_diferencias_de_monto(datos, esperadas):
    *_, resultado = datos
    assert set(resultado.diferencias_monto["comprobante"]) == claves(esperadas, "diferencia_monto", "comprobante")


def test_encuentra_los_duplicados(datos, esperadas):
    *_, resultado = datos
    assert set(resultado.duplicados["comprobante"]) == claves(esperadas, "duplicado", "comprobante")


def test_ningun_movimiento_queda_en_dos_categorias(datos):
    banco, libro, _, resultado = datos
    ids_banco = list(resultado.conciliados["id_banco"]) + list(resultado.diferencias_monto["id_banco"])
    assert len(ids_banco) == len(set(ids_banco))
    assert len(ids_banco) + len(resultado.solo_banco) == len(banco)
    comprobantes = (list(resultado.conciliados["comprobante"]) + list(resultado.diferencias_monto["comprobante"])
                    + list(resultado.duplicados["comprobante"]) + list(resultado.solo_registro["comprobante"]))
    assert sorted(comprobantes) == sorted(libro["comprobante"])


def test_la_conciliacion_cuadra(datos):
    banco, libro, saldo_inicial, resultado = datos
    assert cuadre(resultado, banco, libro, saldo_inicial)["diferencia"] == 0


def tabla(filas):
    return pd.DataFrame(filas, columns=["fecha", "operacion", "monto"]).assign(
        fecha=lambda d: pd.to_datetime(d["fecha"]),
        operacion=lambda d: d["operacion"].astype("string"),
    )


def extracto(filas):
    return tabla(filas).assign(descripcion="")


def registro(filas):
    return tabla(filas).assign(comprobante=[f"CB-{i}" for i in range(len(filas))], glosa="")


def test_un_movimiento_del_banco_no_se_usa_dos_veces():
    banco = extracto([("2026-09-10", "11111111", 100.0)])
    libro = registro([("2026-09-10", None, 100.0), ("2026-09-11", None, 100.0)])
    resultado = conciliar(banco, libro)
    assert len(resultado.conciliados) == 1
    assert len(resultado.solo_registro) == 1


def test_fuera_de_tolerancia_no_concilia():
    banco = extracto([("2026-09-01", "11111111", 250.0)])
    libro = registro([("2026-09-08", None, 250.0)])
    resultado = conciliar(banco, libro)
    assert resultado.conciliados.empty
    assert len(resultado.solo_banco) == 1
    assert len(resultado.solo_registro) == 1
