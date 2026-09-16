"""Verifica el EDA contra los números medidos en CLAUDE.md §8.2 y §8.3.

Como en `test_ingest.py`: si un valor no coincide, es el código el que está
mal, no CLAUDE.md -- no se ajusta el valor esperado para que el test pase.
"""

from __future__ import annotations

import pandas as pd
import pytest

from calidad_aire.eda import (
    ciclo_estacional,
    ciclo_horario,
    cobertura_por_estacion_y_anio,
    comparacion_resolucion,
    episodios,
    reconstruccion_diaria,
    resumen_anual,
)
from tests.conftest import requiere_datos_procesados

ESTACIONES_NUCLEO = ("los_maitenes", "la_greda", "puchuncavi")


@pytest.fixture
def so2_nucleo(tabla_procesada: pd.DataFrame) -> pd.DataFrame:
    so2 = tabla_procesada[tabla_procesada["parametro"].isin(["so2_horario", "so2_diario"])]
    return so2[so2["estacion"].isin(ESTACIONES_NUCLEO)].copy()


@requiere_datos_procesados
class TestEpisodiosContraCLAUDE:
    """CLAUDE.md §8.2: totales de episodios por estación."""

    @pytest.mark.parametrize(
        ("estacion", "esperado_500", "esperado_350"),
        [
            ("los_maitenes", 1_323, 2_494),
            ("la_greda", 354, 772),
            ("puchuncavi", 311, 962),
        ],
    )
    def test_totales_por_estacion(self, so2_nucleo, estacion, esperado_500, esperado_350) -> None:
        ep_500 = episodios(so2_nucleo, umbral=500)
        ep_350 = episodios(so2_nucleo, umbral=350)

        assert ep_500[ep_500["estacion"] == estacion]["n_horas"].sum() == esperado_500
        assert ep_350[ep_350["estacion"] == estacion]["n_horas"].sum() == esperado_350

    @pytest.mark.parametrize(
        ("inicio", "fin", "esperado"),
        [
            (1993, 1999, 1_851),
            (2000, 2009, 132),
            (2010, 2019, 5),
            (2020, 2026, 0),
        ],
    )
    def test_emergencias_por_periodo(self, so2_nucleo, inicio, fin, esperado) -> None:
        ep_500 = episodios(so2_nucleo, umbral=500)
        en_periodo = ep_500[(ep_500["anio"] >= inicio) & (ep_500["anio"] <= fin)]
        assert en_periodo["n_horas"].sum() == esperado

    def test_incluye_anios_sin_episodios_no_los_omite(self, so2_nucleo) -> None:
        ep_500 = episodios(so2_nucleo, umbral=500)
        fila_2024 = ep_500[(ep_500["estacion"] == "los_maitenes") & (ep_500["anio"] == 2024)]
        assert len(fila_2024) == 1
        assert fila_2024["n_horas"].iloc[0] == 0


@requiere_datos_procesados
class TestResumenAnualContraCLAUDE:
    """CLAUDE.md §8.2: máximos anuales por estación, los tres a la vez."""

    @pytest.mark.parametrize(
        ("anio", "esperados"),
        [
            (1995, {"los_maitenes": 997, "la_greda": 998, "puchuncavi": 966}),
            (2018, {"los_maitenes": 480, "la_greda": 307, "puchuncavi": 143}),
            (2023, {"los_maitenes": 357, "la_greda": 90, "puchuncavi": 37}),
            (2024, {"los_maitenes": 29, "la_greda": 16, "puchuncavi": 24}),
            (2025, {"los_maitenes": 39, "la_greda": 14, "puchuncavi": 40}),
            (2026, {"los_maitenes": 36, "la_greda": 18, "puchuncavi": 36}),
        ],
    )
    def test_maximo_anual(self, so2_nucleo, anio, esperados) -> None:
        resumen = resumen_anual(so2_nucleo)
        for estacion, maximo_esperado in esperados.items():
            fila = resumen[(resumen["estacion"] == estacion) & (resumen["anio"] == anio)]
            assert round(fila["maximo"].iloc[0]) == maximo_esperado


@requiere_datos_procesados
class TestReconstruccionDiaria:
    """LA VERIFICACIÓN CENTRAL (CLAUDE.md §8.3). Sin criterio de
    aprobado/reprobado: se fija la distribución completa y los días exactos.
    """

    def test_distribucion_contra_lo_medido(self, tabla_procesada) -> None:
        resultado = reconstruccion_diaria(tabla_procesada)

        assert resultado["n_dias_comparados"] == 9_427
        assert resultado["diferencia_mediana_ug_m3"] == pytest.approx(0.0, abs=1e-3)

        esperado = {
            0.1: (99.830, 16),
            0.5: (99.873, 12),
            1.0: (99.926, 7),
            2.0: (99.958, 4),
            5.0: (100.0, 0),
        }
        por_tolerancia = {f["tolerancia_ug_m3"]: f for f in resultado["distribucion"]}
        for tolerancia, (pct_esperado, n_fuera_esperado) in esperado.items():
            fila = por_tolerancia[tolerancia]
            assert fila["pct_coincide"] == pytest.approx(pct_esperado, abs=1e-3)
            assert fila["n_dias_fuera"] == n_fuera_esperado

    def test_los_siete_dias_discrepantes_son_exactamente_estos(self, tabla_procesada) -> None:
        # Medido a mano (2026-09-16): las siete fechas y su diferencia, todas
        # con cobertura horaria casi completa -- no es un problema de huecos.
        esperado = {
            "2015-12-08": (4.425, 24),
            "2015-01-01": (3.169, 24),
            "2011-10-26": (2.882, 24),
            "2012-10-20": (2.065, 23),
            "2015-03-18": (1.564, 24),
            "2016-02-01": (1.401, 24),
            "2015-12-20": (1.311, 24),
        }
        resultado = reconstruccion_diaria(tabla_procesada)
        dias = {
            d["fecha"]: (d["diferencia_ug_m3"], d["n_horas"])
            for d in resultado["dias_discrepantes"]
        }

        assert set(dias.keys()) == set(esperado.keys())
        for fecha, (diferencia_esperada, n_horas_esperado) in esperado.items():
            diferencia, n_horas = dias[fecha]
            assert diferencia == pytest.approx(diferencia_esperada, abs=1e-3)
            assert n_horas == n_horas_esperado


class TestReconstruccionDiariaSintetica:
    """Unitario, sin depender de los datos reales: verifica la lógica sola."""

    def test_promedio_horario_exacto_no_deja_dias_discrepantes(self) -> None:
        horas = pd.date_range("2020-01-01", periods=48, freq="h")
        valores_horarios = [10.0] * 24 + [30.0] * 24  # medias diarias 10 y 30
        horaria = pd.DataFrame(
            {
                "estacion": "los_maitenes",
                "parametro": "so2_horario",
                "fecha_hora": horas,
                "valor": valores_horarios,
                "estado": "validado",
            }
        )
        diaria = pd.DataFrame(
            {
                "estacion": ["los_maitenes", "los_maitenes"],
                "parametro": ["so2_diario", "so2_diario"],
                "fecha_hora": pd.to_datetime(["2020-01-01", "2020-01-02"]),
                "valor": [10.0, 30.0],
                "estado": ["validado", "validado"],
            }
        )
        df = pd.concat([horaria, diaria], ignore_index=True)

        resultado = reconstruccion_diaria(df)

        assert resultado["n_dias_comparados"] == 2
        assert resultado["diferencia_mediana_ug_m3"] == pytest.approx(0.0)
        assert resultado["dias_discrepantes"] == []
        assert {f["tolerancia_ug_m3"]: f["pct_coincide"] for f in resultado["distribucion"]}[
            0.1
        ] == 100.0

    def test_diferencia_grande_queda_en_dias_discrepantes(self) -> None:
        horas = pd.date_range("2020-01-01", periods=24, freq="h")
        horaria = pd.DataFrame(
            {
                "estacion": "los_maitenes",
                "parametro": "so2_horario",
                "fecha_hora": horas,
                "valor": [10.0] * 24,  # media diaria real = 10
                "estado": "validado",
            }
        )
        diaria = pd.DataFrame(
            {
                "estacion": ["los_maitenes"],
                "parametro": ["so2_diario"],
                "fecha_hora": pd.to_datetime(["2020-01-01"]),
                "valor": [500.0],  # deliberadamente incompatible
                "estado": ["validado"],
            }
        )
        df = pd.concat([horaria, diaria], ignore_index=True)

        resultado = reconstruccion_diaria(df)

        assert resultado["n_dias_comparados"] == 1
        assert resultado["diferencia_mediana_ug_m3"] == pytest.approx(490.0)
        assert len(resultado["dias_discrepantes"]) == 1
        assert resultado["dias_discrepantes"][0]["fecha"] == "2020-01-01"
        assert resultado["dias_discrepantes"][0]["diferencia_ug_m3"] == pytest.approx(490.0)
        assert resultado["dias_discrepantes"][0]["n_horas"] == 24


@requiere_datos_procesados
class TestComparacionResolucion:
    """LA DEMOSTRACIÓN (CLAUDE.md §8.3): diario-vs-horario en los_maitenes."""

    def test_contra_los_valores_esperados(self, tabla_procesada) -> None:
        resultado = comparacion_resolucion(tabla_procesada)

        assert resultado["superaciones_diarias"] == 2
        assert resultado["superaciones_diarias_desde_2019"] == 0
        assert resultado["horas_emergencia"] == 1_323
        assert resultado["maximo_diario_ug_m3"] == pytest.approx(157.58, abs=0.01)

    def test_horas_emergencia_es_dos_ordenes_de_magnitud_mayor(self, tabla_procesada) -> None:
        resultado = comparacion_resolucion(tabla_procesada)
        assert resultado["horas_emergencia"] > 100 * resultado["superaciones_diarias"]


@requiere_datos_procesados
class TestCoberturaPorEstacionYAnio:
    def test_porcentaje_entre_0_y_100(self, tabla_procesada) -> None:
        cobertura = cobertura_por_estacion_y_anio(tabla_procesada)
        assert cobertura["cobertura_pct"].between(0, 100).all()

    def test_horas_con_valor_no_supera_horas_totales(self, tabla_procesada) -> None:
        cobertura = cobertura_por_estacion_y_anio(tabla_procesada)
        assert (cobertura["horas_con_valor"] <= cobertura["horas_totales"]).all()


@requiere_datos_procesados
class TestCiclos:
    def test_ciclo_horario_cubre_las_24_horas_y_suma_el_total(self, so2_nucleo) -> None:
        ciclo = ciclo_horario(so2_nucleo, umbral=500)
        assert list(ciclo["hora"]) == list(range(24))
        assert ciclo["n_episodios"].sum() == 1_988  # 1323 + 354 + 311, CLAUDE.md §8.2

    def test_ciclo_estacional_cubre_los_12_meses_y_suma_el_total(self, so2_nucleo) -> None:
        ciclo = ciclo_estacional(so2_nucleo, umbral=500)
        assert list(ciclo["mes"]) == list(range(1, 13))
        assert ciclo["n_episodios"].sum() == 1_988
