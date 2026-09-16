"""Verifica la ingesta contra los números medidos en CLAUDE.md §8.1 y §8.2.

Tolerancia 1e-3 salvo en conteos enteros, que deben coincidir exactamente. Si
un valor no coincide, es la ingesta la que está mal, no CLAUDE.md: no se
ajusta el valor esperado para que el test pase (CLAUDE.md, cabecera).
"""

from datetime import datetime
from pathlib import Path

import pytest

from calidad_aire.ingest import FormatoSincaError, leer_sinca, parse_fecha_hora
from tests.conftest import RAW_DIR, requiere_datos_crudos


class TestReglaDelSiglo:
    def test_yy_menor_que_50_es_2000(self) -> None:
        assert parse_fecha_hora("260101", "0100") == datetime(2026, 1, 1, 1, 0)

    def test_yy_50_o_mayor_es_1900(self) -> None:
        assert parse_fecha_hora("700101", "0100") == datetime(1970, 1, 1, 1, 0)

    def test_frontera_49_vs_50(self) -> None:
        assert parse_fecha_hora("490101", "0100").year == 2049
        assert parse_fecha_hora("500101", "0100").year == 1950


class TestFormatoSincaError:
    def test_tabla_resumen_falla_con_mensaje_claro(self, tmp_path: Path) -> None:
        # Una tabla resumen (rosa de vientos) no tiene FECHA;HORA por fila.
        resumen = tmp_path / "resumen_rosa_vientos.csv"
        resumen.write_text("N;NE;E;SE;S;SO;O;NO\n12;8;4;6;10;15;20;25\n", encoding="latin-1")

        with pytest.raises(FormatoSincaError, match="tabla resumen"):
            leer_sinca(resumen)

    def test_fichero_vacio_falla_con_mensaje_claro(self, tmp_path: Path) -> None:
        vacio = tmp_path / "vacio.csv"
        vacio.write_text("", encoding="latin-1")

        with pytest.raises(FormatoSincaError, match="vacío"):
            leer_sinca(vacio)


@requiere_datos_crudos
class TestEpisodiosSo2:
    """Contra CLAUDE.md §8.2: horas válidas y episodios por estación."""

    def test_los_maitenes_so2_horario(self) -> None:
        df = leer_sinca(RAW_DIR / "los_maitenes" / "so2_horario.csv")

        assert df["valor"].notna().sum() == 287_088
        assert (df["valor"] >= 500).sum() == 1_323
        assert (df["valor"] >= 350).sum() == 2_494

    def test_la_greda_so2_horario(self) -> None:
        df = leer_sinca(RAW_DIR / "la_greda" / "so2_horario.csv")

        assert df["valor"].notna().sum() == 292_514
        assert (df["valor"] >= 500).sum() == 354

    def test_puchuncavi_so2_horario(self) -> None:
        df = leer_sinca(RAW_DIR / "puchuncavi" / "so2_horario.csv")

        assert df["valor"].notna().sum() == 293_070
        assert (df["valor"] >= 500).sum() == 311


@requiere_datos_crudos
class TestEmergenciasPorPeriodo:
    """Contra CLAUDE.md §8.2: horas de emergencia sumadas en las tres estaciones."""

    @classmethod
    @pytest.fixture(scope="class")
    def emergencias(cls, tabla_consolidada):
        estaciones = ("los_maitenes", "la_greda", "puchuncavi")
        so2 = tabla_consolidada[
            (tabla_consolidada["parametro"] == "so2_horario")
            & (tabla_consolidada["estacion"].isin(estaciones))
        ].copy()
        so2["anio"] = so2["fecha_hora"].dt.year
        return so2[so2["valor"] >= 500]

    @pytest.mark.parametrize(
        ("inicio", "fin", "esperado"),
        [
            (1993, 1999, 1_851),
            (2000, 2009, 132),
            (2010, 2019, 5),
            (2020, 2026, 0),
        ],
    )
    def test_horas_en_emergencia_por_periodo(self, emergencias, inicio, fin, esperado) -> None:
        n = emergencias[(emergencias["anio"] >= inicio) & (emergencias["anio"] <= fin)].shape[0]
        assert n == esperado


@requiere_datos_crudos
def test_consolidar_incluye_las_cinco_estaciones(tabla_consolidada) -> None:
    esperadas = {"la_greda", "las_palmas", "los_maitenes", "puchuncavi", "ventanas"}
    assert set(tabla_consolidada["estacion"].unique()) == esperadas
