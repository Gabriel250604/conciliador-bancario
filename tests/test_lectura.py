from pathlib import Path

import pytest

from lectura import leer_extracto, leer_libro

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(scope="module")
def extracto():
    return leer_extracto(DATA / "extracto_banco.csv")


@pytest.fixture(scope="module")
def libro():
    return leer_libro(DATA / "libro_bancos.xlsx")


def test_extracto_lee_todos_los_movimientos(extracto):
    movimientos, saldo_inicial = extracto
    assert len(movimientos) == 122
    assert saldo_inicial == 120000.00


def test_extracto_cuadra_con_el_saldo_final(extracto):
    movimientos, saldo_inicial = extracto
    assert round(saldo_inicial + movimientos["monto"].sum(), 2) == 65132.67


def test_operaciones_del_extracto_tienen_ocho_digitos(extracto):
    movimientos, _ = extracto
    assert movimientos["operacion"].str.fullmatch(r"\d{8}").all()


def test_libro_lee_todos_los_asientos(libro):
    assert len(libro) == 120
    assert libro["operacion"].isna().sum() == 20


def test_libro_recupera_los_ceros_iniciales(libro, extracto):
    movimientos, _ = extracto
    operaciones = set(libro["operacion"].dropna())
    assert any(op.startswith("0") for op in operaciones)
    assert operaciones <= set(movimientos["operacion"])


def test_saldo_alterado_se_detecta(tmp_path):
    lineas = (DATA / "extracto_banco.csv").read_text(encoding="cp1252").splitlines()
    ultima = lineas[-1].split(";")
    ultima[-1] = "99,999.99"
    lineas[-1] = ";".join(ultima)
    alterado = tmp_path / "extracto.csv"
    alterado.write_text("\n".join(lineas), encoding="cp1252")
    with pytest.raises(ValueError, match="no cuadra"):
        leer_extracto(alterado)