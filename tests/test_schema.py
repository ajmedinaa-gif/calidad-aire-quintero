"""Contrato de datos: rangos físicos y cuarentena (CLAUDE.md, regla dura 4)."""

from datetime import datetime

import pandas as pd
import pytest

from calidad_aire.data import load_validated
from calidad_aire.ingest import leer_sinca
from tests.conftest import RAW_DIR, requiere_datos_crudos


def _fila(**kwargs) -> dict:
    base = {
        "estacion": "los_maitenes",
        "parametro": "so2_horario",
        "fecha_hora": datetime(2024, 1, 1, 12, 0),
        "valor": 10.0,
        "estado": "validado",
    }
    base.update(kwargs)
    return base


class TestRangosFisicos:
    def test_concentracion_negativa_va_a_cuarentena(self, tmp_path) -> None:
        df = pd.DataFrame([_fila(valor=-1.0)])
        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)

        assert validas.empty
        assert len(cuarentena) == 1
        assert "rango físico" in cuarentena.iloc[0]["motivo"]

    def test_direccion_viento_sobre_360_va_a_cuarentena(self, tmp_path) -> None:
        df = pd.DataFrame([_fila(parametro="direccion_viento_horario", valor=400.0)])
        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)

        assert validas.empty
        assert len(cuarentena) == 1

    def test_velocidad_viento_sobre_60_va_a_cuarentena(self, tmp_path) -> None:
        df = pd.DataFrame([_fila(parametro="velocidad_viento_horario", valor=90_114.5)])
        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)

        assert validas.empty
        assert len(cuarentena) == 1

    def test_valor_nulo_es_valido_ausente_no_es_imposible(self, tmp_path) -> None:
        df = pd.DataFrame([_fila(valor=float("nan"), estado="ausente")])
        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)

        assert len(validas) == 1
        assert cuarentena.empty

    def test_valores_dentro_de_rango_pasan(self, tmp_path) -> None:
        df = pd.DataFrame(
            [
                _fila(valor=349.9),
                _fila(parametro="direccion_viento_horario", valor=359.0),
                _fila(parametro="velocidad_viento_horario", valor=59.9),
            ]
        )
        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)

        assert len(validas) == 3
        assert cuarentena.empty

    def test_filas_en_cuarentena_se_escriben_a_disco(self, tmp_path) -> None:
        df = pd.DataFrame([_fila(valor=-1.0)])
        load_validated(df, quarantine_dir=tmp_path)

        ficheros = list(tmp_path.glob("*.csv"))
        assert len(ficheros) == 1
        assert "motivo" in pd.read_csv(ficheros[0]).columns


@requiere_datos_crudos
class TestCuarentenaSobreDatosReales:
    """La_greda tiene la lectura imposible de 90.114,5 m/s (CLAUDE.md §8.6.2)."""

    @classmethod
    @pytest.fixture(scope="class")
    def resultado(cls, tmp_path_factory):
        crudo = leer_sinca(RAW_DIR / "la_greda" / "velocidad_viento_horario.csv")
        crudo.insert(0, "parametro", "velocidad_viento_horario")
        crudo.insert(0, "estacion", "la_greda")
        destino = tmp_path_factory.mktemp("cuarentena")
        return load_validated(crudo, quarantine_dir=destino)

    def test_90114_metros_por_segundo_va_a_cuarentena(self, resultado) -> None:
        _validas, cuarentena = resultado
        con_90114 = cuarentena[cuarentena["valor"] == 90_114.5]

        assert len(con_90114) > 0
        assert (con_90114["motivo"] == "valor fuera de rango físico").all()

    def test_cuarentena_no_esta_vacia_pero_es_minoritaria(self, resultado) -> None:
        validas, cuarentena = resultado
        # Reporta el tamaño real: en la_greda/velocidad_viento_horario.csv es
        # una minoría de filas frente al total, no una fracción relevante.
        assert 0 < len(cuarentena) < len(validas) * 0.01
