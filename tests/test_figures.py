"""Las funciones de figuras guardan un PNG legible (CLAUDE.md §14.4).

No se inspecciona el contenido visual -- eso lo hace la usuaria mirando el
PNG en `reports/figures/` -- solo que cada función escribe un fichero no
vacío en la ruta pedida y cierra la figura sin lanzar.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from calidad_aire import figures


def _es_png_no_vacio(path: Path) -> bool:
    return path.exists() and path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def _horaria(estacion: str, inicio: str, valores: list[float]) -> pd.DataFrame:
    horas = pd.date_range(inicio, periods=len(valores), freq="h")
    return pd.DataFrame(
        {
            "estacion": estacion,
            "parametro": "so2_horario",
            "fecha_hora": horas,
            "valor": valores,
            "estado": "validado",
        }
    )


@pytest.fixture
def episodios_sinteticos() -> pd.DataFrame:
    filas = [
        {"estacion": estacion, "anio": anio, "n_horas": 5}
        for estacion in figures.ESTACIONES_NUCLEO
        for anio in (2018, 2019, 2020)
    ]
    return pd.DataFrame(filas)


@pytest.fixture
def resumen_sintetico() -> pd.DataFrame:
    filas = [
        {
            "estacion": estacion,
            "anio": anio,
            "n": 100,
            "media": 20.0,
            "p99": 300.0,
            "maximo": 400.0,
            "horas_350": 3,
            "horas_500": 1,
        }
        for estacion in figures.ESTACIONES_NUCLEO
        for anio in (2018, 2019, 2020)
    ]
    return pd.DataFrame(filas)


@pytest.fixture
def so2_sintetico() -> pd.DataFrame:
    # 168 horas (una semana), con un pico de emergencia cada día a mediodía.
    valores = [600.0 if i % 24 == 12 else 10.0 for i in range(168)]
    return _horaria("los_maitenes", "1995-01-02", valores)


class TestFiguras:
    def test_serie_anual_emergencias(self, episodios_sinteticos, tmp_path) -> None:
        destino = figures.figura_serie_anual_emergencias(episodios_sinteticos, tmp_path / "a.png")
        assert _es_png_no_vacio(destino)

    def test_maximo_anual(self, resumen_sintetico, tmp_path) -> None:
        destino = figures.figura_maximo_anual(resumen_sintetico, tmp_path / "b.png")
        assert _es_png_no_vacio(destino)

    def test_clave_resolucion(self, so2_sintetico, tmp_path) -> None:
        destino = figures.figura_clave_resolucion(
            so2_sintetico,
            tmp_path / "c.png",
            inicio="1995-01-02",
            fin_exclusivo="1995-01-09",
        )
        assert _es_png_no_vacio(destino)

    def test_clave_resolucion_sin_datos_en_la_ventana_no_lanza(
        self, so2_sintetico, tmp_path
    ) -> None:
        # so2_sintetico solo cubre enero de 1995: pedir una ventana sin datos
        # no debe romper el eje Y compartido (bug real: NaN en set_ylim).
        destino = figures.figura_clave_resolucion(
            so2_sintetico,
            tmp_path / "c_vacia.png",
            inicio="2000-01-01",
            fin_exclusivo="2000-01-08",
        )
        assert _es_png_no_vacio(destino)

    def test_mapa_calor_ciclo(self, so2_sintetico, tmp_path) -> None:
        destino = figures.figura_mapa_calor_ciclo(
            so2_sintetico, tmp_path / "d.png", estaciones=("los_maitenes",)
        )
        assert _es_png_no_vacio(destino)

    def test_cobertura(self, tmp_path) -> None:
        cobertura = pd.DataFrame(
            {
                "estacion": ["los_maitenes", "los_maitenes", "la_greda", "la_greda"],
                "anio": [2020, 2021, 2020, 2021],
                "horas_totales": [8760, 8760, 8760, 8760],
                "horas_con_valor": [8000, 8500, 7000, 7500],
                "cobertura_pct": [91.3, 97.0, 79.9, 85.6],
            }
        )
        destino = figures.figura_cobertura(cobertura, tmp_path / "e.png")
        assert _es_png_no_vacio(destino)

    def test_crea_el_directorio_padre_si_no_existe(self, episodios_sinteticos, tmp_path) -> None:
        destino = figures.figura_serie_anual_emergencias(
            episodios_sinteticos, tmp_path / "anidado" / "mas" / "f.png"
        )
        assert _es_png_no_vacio(destino)
