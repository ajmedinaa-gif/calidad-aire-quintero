"""Figuras de la fase de EDA (CLAUDE.md §8.3), en `reports/figures/`.

`matplotlib.use("Agg")` se fija antes de importar `pyplot` (CLAUDE.md §14.4):
esta máquina no tiene interfaz gráfica. Cada función recibe los datos ya
calculados por `eda.py`, dibuja, guarda con `fig.savefig` y cierra la figura
con `plt.close(fig)` -- nunca `plt.show()`.

Paleta de dos colores, consistente en todas las figuras:
- `COLOR_BASE` para la serie o el valor normal.
- `COLOR_EMERGENCIA` para lo que supera el umbral de emergencia ambiental o
  para marcar el evento del cierre.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

COLOR_BASE = "#1f6f8b"
COLOR_EMERGENCIA = "#c1432c"

FECHA_CIERRE = pd.Timestamp("2023-05-31")
UMBRAL_EMERGENCIA_UG_M3 = 500
UMBRAL_NORMA_DIARIA_UG_M3 = 150

ESTACIONES_NUCLEO = ("los_maitenes", "la_greda", "puchuncavi")

# Nombres de presentación: el identificador interno (usado en el código y en
# los JSON de `reports/`) no cambia -- esto es solo la capa de las figuras.
NOMBRE_ESTACION = {
    "los_maitenes": "Los Maitenes",
    "la_greda": "La Greda",
    "puchuncavi": "Puchuncaví",
    "ventanas": "Ventanas",
    "las_palmas": "Las Palmas",
}


def _nombre(estacion: str) -> str:
    return NOMBRE_ESTACION.get(estacion, estacion.replace("_", " "))


def _guardar(fig: plt.Figure, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def figura_serie_anual_emergencias(
    episodios_df: pd.DataFrame,
    path: Path | str,
    estaciones: tuple[str, ...] = ESTACIONES_NUCLEO,
) -> Path:
    """Horas en emergencia por año, las tres estaciones núcleo superpuestas."""
    fig, ax = plt.subplots(figsize=(9, 5))
    colores = {estaciones[0]: COLOR_BASE, estaciones[1]: COLOR_EMERGENCIA, estaciones[2]: "#5a5a5a"}

    for estacion in estaciones:
        serie = episodios_df[episodios_df["estacion"] == estacion].sort_values("anio")
        ax.plot(
            serie["anio"],
            serie["n_horas"],
            marker="o",
            markersize=3,
            linewidth=1.5,
            label=_nombre(estacion),
            color=colores.get(estacion),
        )

    ax.set_title("Horas en nivel de emergencia ambiental por año (SO₂ ≥ 500 µg/m³)")
    ax.set_xlabel("Año")
    ax.set_ylabel("Horas en emergencia")
    ax.legend(title="Estación")
    ax.grid(axis="y", alpha=0.3)

    return _guardar(fig, path)


def figura_maximo_anual(
    resumen_anual_df: pd.DataFrame,
    path: Path | str,
    estaciones: tuple[str, ...] = ESTACIONES_NUCLEO,
) -> Path:
    """Máximo anual por estación, con línea vertical en el cierre (2023-05-31)."""
    fig, ax = plt.subplots(figsize=(9, 5))
    colores = {estaciones[0]: COLOR_BASE, estaciones[1]: COLOR_EMERGENCIA, estaciones[2]: "#5a5a5a"}

    for estacion in estaciones:
        serie = resumen_anual_df[resumen_anual_df["estacion"] == estacion].sort_values("anio")
        fechas = pd.to_datetime(serie["anio"].astype(str) + "-07-01")
        ax.plot(
            fechas,
            serie["maximo"],
            marker="o",
            markersize=3,
            linewidth=1.5,
            label=_nombre(estacion),
            color=colores.get(estacion),
        )

    ax.axhline(
        UMBRAL_EMERGENCIA_UG_M3,
        color="#999999",
        linestyle=":",
        linewidth=1,
        label="emergencia (500 µg/m³)",
    )
    ax.axvline(
        FECHA_CIERRE,
        color="black",
        linestyle="--",
        linewidth=1.2,
        label="cierre Fundición Ventanas (2023-05-31)",
    )

    ax.set_title("Máximo anual de SO₂ por estación")
    ax.set_xlabel("Año")
    ax.set_ylabel("Máximo horario (µg/m³)")
    ax.legend(title="Estación")
    ax.grid(axis="y", alpha=0.3)

    return _guardar(fig, path)


def figura_clave_resolucion(
    df: pd.DataFrame,
    path: Path | str,
    estacion: str = "los_maitenes",
    inicio: str = "1995-01-02",
    fin_exclusivo: str = "1995-01-09",
) -> Path:
    """LA FIGURA CLAVE: la misma semana de 1995 en dos resoluciones.

    Arriba, la serie horaria con sus picos sobre el umbral de emergencia (500
    µg/m³). Abajo, el promedio diario de esa misma semana: plano, y muy por
    debajo incluso de la norma de 24 h (150 µg/m³). Semana elegida porque
    tiene cobertura horaria casi completa y varias horas de emergencia reales
    (verificado en `tests/test_eda.py`), no porque sea la de mayor pico.
    """
    inicio_ts = pd.Timestamp(inicio)
    fin_ts = pd.Timestamp(fin_exclusivo)

    horaria = df[
        (df["estacion"] == estacion)
        & (df["parametro"] == "so2_horario")
        & (df["fecha_hora"] >= inicio_ts)
        & (df["fecha_hora"] < fin_ts)
    ].sort_values("fecha_hora")

    diaria = horaria.set_index("fecha_hora").resample("D")["valor"].mean().reset_index()
    diaria.columns = ["fecha", "valor"]

    fig, (ax_arriba, ax_abajo) = plt.subplots(
        2, 1, figsize=(9, 7), sharex=True, sharey=True, gridspec_kw={"height_ratios": [2, 1]}
    )

    ax_arriba.plot(horaria["fecha_hora"], horaria["valor"], color=COLOR_BASE, linewidth=1.2)
    picos = horaria[horaria["valor"] >= UMBRAL_EMERGENCIA_UG_M3]
    ax_arriba.scatter(picos["fecha_hora"], picos["valor"], color=COLOR_EMERGENCIA, zorder=3, s=25)
    ax_arriba.axhline(
        UMBRAL_EMERGENCIA_UG_M3,
        color=COLOR_EMERGENCIA,
        linestyle="--",
        linewidth=1,
        label="emergencia (500 µg/m³)",
    )
    ax_arriba.set_title(f"Resolución horaria — {_nombre(estacion)}, {inicio} a {fin_exclusivo}")
    ax_arriba.set_ylabel("SO₂ horario (µg/m³)")
    ax_arriba.legend(loc="upper right", fontsize=8)
    ax_arriba.grid(axis="y", alpha=0.3)

    ax_abajo.plot(diaria["fecha"], diaria["valor"], color=COLOR_BASE, marker="o", linewidth=1.5)
    ax_abajo.axhline(
        UMBRAL_NORMA_DIARIA_UG_M3,
        color="#999999",
        linestyle=":",
        linewidth=1,
        label="norma 24 h (150 µg/m³)",
    )
    ax_abajo.set_title("La misma semana, promediada a resolución diaria")
    ax_abajo.set_ylabel("SO₂ diario (µg/m³)")
    ax_abajo.set_xlabel("Fecha")
    ax_abajo.legend(loc="upper right", fontsize=8)
    ax_abajo.grid(axis="y", alpha=0.3)

    # Mismo límite Y en los dos paneles -- a propósito (CLAUDE.md §8.3): así
    # se ve que la serie diaria no está "recortada", sino genuinamente plana
    # frente a los picos horarios, sobre la misma escala.
    maximo_horario = horaria["valor"].max()
    if pd.isna(maximo_horario):
        maximo_horario = UMBRAL_EMERGENCIA_UG_M3
    ax_arriba.set_ylim(0, max(maximo_horario, UMBRAL_EMERGENCIA_UG_M3) * 1.05)

    fig.suptitle("")
    fig.text(0.5, -0.01, "mismo dato, dos resoluciones", ha="center", fontsize=10, style="italic")

    return _guardar(fig, path)


def figura_mapa_calor_ciclo(
    df: pd.DataFrame,
    path: Path | str,
    umbral: float = UMBRAL_EMERGENCIA_UG_M3,
    estaciones: tuple[str, ...] = ESTACIONES_NUCLEO,
) -> Path:
    """Mapa de calor hora del día x mes de las horas de emergencia."""
    sub = df[
        (df["parametro"] == "so2_horario")
        & (df["estacion"].isin(estaciones))
        & (df["valor"] >= umbral)
    ].copy()
    sub["hora"] = sub["fecha_hora"].dt.hour
    sub["mes"] = sub["fecha_hora"].dt.month

    matriz = (
        sub.groupby(["hora", "mes"])
        .size()
        .unstack("mes")
        .reindex(index=range(24), columns=range(1, 13))
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(9, 6))
    malla = ax.pcolormesh(
        matriz.columns, matriz.index, matriz.to_numpy(), cmap="YlOrRd", shading="auto"
    )
    fig.colorbar(malla, ax=ax, label="Horas de emergencia")

    ax.set_title(f"Hora del día y mes de las horas de emergencia (SO₂ ≥ {umbral} µg/m³)")
    ax.set_xlabel("Mes")
    ax.set_ylabel("Hora del día")
    ax.set_xticks(range(1, 13))
    ax.set_yticks(range(0, 24, 2))

    return _guardar(fig, path)


def figura_cobertura(cobertura_df: pd.DataFrame, path: Path | str) -> Path:
    """Cobertura de datos (%) por estación y año, como mapa de calor."""
    matriz = cobertura_df.pivot(index="estacion", columns="anio", values="cobertura_pct")

    fig, ax = plt.subplots(figsize=(12, 4))
    malla = ax.pcolormesh(
        matriz.columns,
        range(len(matriz.index)),
        matriz.to_numpy(),
        cmap="YlGnBu",
        vmin=0,
        vmax=100,
        shading="auto",
    )
    fig.colorbar(malla, ax=ax, label="Cobertura (%)")

    ax.set_yticks(range(len(matriz.index)))
    ax.set_yticklabels([_nombre(e) for e in matriz.index])
    ax.set_xlabel("Año")
    ax.set_title("Cobertura de datos de SO₂ por estación y año")

    return _guardar(fig, path)
