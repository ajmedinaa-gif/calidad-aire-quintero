"""Contrato de datos: rangos físicos y cuarentena (CLAUDE.md, regla dura 4)."""

from datetime import datetime

import pandas as pd
import pytest

from calidad_aire.data import descartar_ausentes_antes_de_operacion, load_validated
from calidad_aire.ingest import leer_sinca
from calidad_aire.schema import INICIO_OPERACION
from tests.conftest import RAW_DIR, requiere_datos_crudos, requiere_datos_procesados


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
        # los_maitenes nunca midió viento (CLAUDE.md §8.6.4); puchuncavi sí.
        df = pd.DataFrame(
            [_fila(estacion="puchuncavi", parametro="direccion_viento_horario", valor=400.0)]
        )
        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)

        assert validas.empty
        assert len(cuarentena) == 1

    def test_velocidad_viento_sobre_60_va_a_cuarentena(self, tmp_path) -> None:
        df = pd.DataFrame(
            [_fila(estacion="puchuncavi", parametro="velocidad_viento_horario", valor=90_114.5)]
        )
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
                _fila(estacion="puchuncavi", parametro="direccion_viento_horario", valor=359.0),
                _fila(estacion="puchuncavi", parametro="velocidad_viento_horario", valor=59.9),
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
        # Motivo contiene "valor fuera de rango físico" siempre, pero puede
        # venir combinado con "fecha_anterior_a_operacion" cuando la lectura
        # además cae antes de 2010 (CLAUDE.md §8.6.4): 3 de las 4 ocurrencias
        # de 90.114,5 en la_greda son de 1970 y 1987, antes de esa fecha.
        assert con_90114["motivo"].str.contains("valor fuera de rango físico").all()

    def test_cuarentena_no_esta_vacia_pero_es_minoritaria(self, resultado) -> None:
        validas, cuarentena = resultado
        # Reporta el tamaño real: en la_greda/velocidad_viento_horario.csv es
        # una minoría de filas frente al total, no una fracción relevante.
        assert 0 < len(cuarentena) < len(validas) * 0.01


class TestInicioOperacion:
    """CLAUDE.md §8.6.4: la fecha mínima ya no es un epoch global de 1970."""

    def test_fila_nula_antes_de_operacion_se_descarta_en_silencio(self) -> None:
        df = pd.DataFrame(
            [_fila(estacion="la_greda", parametro="velocidad_viento_horario", valor=float("nan"))]
        )
        df.loc[0, "fecha_hora"] = datetime(1980, 1, 1)

        filtrado = descartar_ausentes_antes_de_operacion(df)
        assert filtrado.empty

        validas, cuarentena = load_validated(df, quarantine_dir=None)
        assert validas.empty
        assert cuarentena.empty

    def test_fila_con_valor_antes_de_operacion_va_a_cuarentena(self, tmp_path) -> None:
        df = pd.DataFrame(
            [_fila(estacion="la_greda", parametro="velocidad_viento_horario", valor=5.0)]
        )
        df.loc[0, "fecha_hora"] = datetime(1980, 1, 1)

        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)
        assert validas.empty
        assert len(cuarentena) == 1
        assert "fecha_anterior_a_operacion" in cuarentena.iloc[0]["motivo"]

    def test_fila_despues_de_operacion_pasa(self, tmp_path) -> None:
        df = pd.DataFrame(
            [_fila(estacion="la_greda", parametro="velocidad_viento_horario", valor=5.0)]
        )
        df.loc[0, "fecha_hora"] = datetime(2015, 1, 1)

        validas, cuarentena = load_validated(df, quarantine_dir=tmp_path)
        assert len(validas) == 1
        assert cuarentena.empty

    def test_par_desconocido_falla_ruidosamente(self, tmp_path) -> None:
        df = pd.DataFrame([_fila(estacion="una_estacion_inventada", valor=5.0)])

        with pytest.raises(ValueError, match="INICIO_OPERACION"):
            load_validated(df, quarantine_dir=tmp_path)


@requiere_datos_procesados
def test_parquet_no_tiene_filas_anteriores_a_su_inicio_de_operacion(tabla_procesada) -> None:
    """Regresión: ninguna fila del parquet real debe preceder a su estación."""
    infracciones = []
    for (estacion, parametro), inicio in INICIO_OPERACION.items():
        sub = tabla_procesada[
            (tabla_procesada["estacion"] == estacion) & (tabla_procesada["parametro"] == parametro)
        ]
        antes = sub[sub["fecha_hora"] < inicio]
        if not antes.empty:
            infracciones.append((estacion, parametro, len(antes)))

    assert infracciones == []
