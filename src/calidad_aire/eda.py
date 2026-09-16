"""Análisis exploratorio y la demostración de que el dato público diario no
puede mostrar los episodios (CLAUDE.md §8.3).

Funciones puras: reciben el `DataFrame` consolidado (columnas `estacion`,
`parametro`, `fecha_hora`, `valor`, `estado`) y devuelven `DataFrame`/`dict`,
sin leer ni escribir ficheros -- eso vive en `cli.py`.

`reconstruccion_diaria` es LA VERIFICACIÓN CENTRAL de esta fase: si su
resultado no coincide con los números de CLAUDE.md §8.3, la ingesta está mal
y hay que pararse ahí, no seguir construyendo encima.
"""

from __future__ import annotations

import pandas as pd

SO2_HORARIO = "so2_horario"
SO2_DIARIO = "so2_diario"

UMBRAL_NORMA_HORARIA_UG_M3 = 350
UMBRAL_NORMA_DIARIA_UG_M3 = 150
UMBRAL_EMERGENCIA_UG_M3 = 500

ESTACION_RECONSTRUCCION = "los_maitenes"

# CLAUDE.md §8.3 exige "coincide en 99,9 % con diferencia mediana 0,000",
# pero la fuente de SINCA en sí trae discrepancias de hasta ~4,4 µg/m³ en un
# puñado de días completos de 24 horas (no achacables a huecos de cobertura;
# medido y confirmado). 1 µg/m³ -- menos del 1 % de la norma horaria -- es la
# tolerancia más pequeña que reproduce el 99,9 % declarado; por debajo de eso
# se cae a 99,8 %. Ver tests/test_eda.py::test_reconstruccion_diaria.
TOLERANCIA_RECONSTRUCCION_UG_M3 = 1.0


def _a_tipo_nativo(valor):
    return valor.item() if hasattr(valor, "item") else valor


def registros(df: pd.DataFrame) -> list[dict]:
    """`DataFrame` -> lista de dicts con tipos nativos de Python (para JSON)."""
    return [{k: _a_tipo_nativo(v) for k, v in fila.items()} for fila in df.to_dict("records")]


def cobertura_por_estacion_y_anio(df: pd.DataFrame, parametro: str = SO2_HORARIO) -> pd.DataFrame:
    """% de horas con valor, por estación y año, para `parametro`.

    SINCA entrega una fila por hora aunque no haya medición (estado
    "ausente"), así que el denominador es el número de filas que la propia
    fuente reporta ese año para esa estación -- no 8760/8784 fijo -- lo que
    deja la cobertura correcta también en los años parciales de inicio y fin
    de cada serie.
    """
    sub = df[df["parametro"] == parametro].copy()
    sub["anio"] = sub["fecha_hora"].dt.year

    g = sub.groupby(["estacion", "anio"], observed=True)["valor"]
    resumen = g.agg(horas_totales="size", horas_con_valor="count").reset_index()
    resumen["cobertura_pct"] = resumen["horas_con_valor"] / resumen["horas_totales"] * 100

    return resumen.sort_values(["estacion", "anio"]).reset_index(drop=True)


def episodios(
    df: pd.DataFrame, umbral: float = UMBRAL_EMERGENCIA_UG_M3, parametro: str = SO2_HORARIO
) -> pd.DataFrame:
    """Conteo de horas con valor >= `umbral`, por estación y año.

    Incluye años sin ningún episodio con `n_horas = 0` (no los omite): es lo
    que hace visible el desplome a cero desde 2020 en una serie temporal sin
    huecos.
    """
    sub = df[df["parametro"] == parametro].dropna(subset=["valor"]).copy()
    sub["anio"] = sub["fecha_hora"].dt.year

    todos_los_anios = sub[["estacion", "anio"]].drop_duplicates()
    superaciones = sub[sub["valor"] >= umbral]
    conteo = superaciones.groupby(["estacion", "anio"], observed=True).size().rename("n_horas")

    resultado = todos_los_anios.merge(conteo, on=["estacion", "anio"], how="left")
    resultado["n_horas"] = resultado["n_horas"].fillna(0).astype(int)

    return resultado.sort_values(["estacion", "anio"]).reset_index(drop=True)


def resumen_anual(df: pd.DataFrame, parametro: str = SO2_HORARIO) -> pd.DataFrame:
    """Por estación y año: n, media, p99, máximo, horas >=350, horas >=500."""
    sub = df[df["parametro"] == parametro].dropna(subset=["valor"]).copy()
    sub["anio"] = sub["fecha_hora"].dt.year

    filas = []
    for (estacion, anio), grupo in sub.groupby(["estacion", "anio"], observed=True):
        valor = grupo["valor"]
        filas.append(
            {
                "estacion": estacion,
                "anio": int(anio),
                "n": int(valor.shape[0]),
                "media": float(valor.mean()),
                "p99": float(valor.quantile(0.99)),
                "maximo": float(valor.max()),
                "horas_350": int((valor >= UMBRAL_NORMA_HORARIA_UG_M3).sum()),
                "horas_500": int((valor >= UMBRAL_EMERGENCIA_UG_M3).sum()),
            }
        )

    resumen = pd.DataFrame(
        filas,
        columns=["estacion", "anio", "n", "media", "p99", "maximo", "horas_350", "horas_500"],
    )
    return resumen.sort_values(["estacion", "anio"]).reset_index(drop=True)


def ciclo_horario(
    df: pd.DataFrame, umbral: float = UMBRAL_EMERGENCIA_UG_M3, parametro: str = SO2_HORARIO
) -> pd.DataFrame:
    """A qué hora del día (0-23) caen las horas >= `umbral`.

    Suma todas las estaciones presentes en `df`: es información operativa
    (¿a qué hora vigilar?), no un desglose por instrumento.
    """
    sub = df[(df["parametro"] == parametro) & (df["valor"] >= umbral)]
    conteo = sub["fecha_hora"].dt.hour.value_counts().reindex(range(24), fill_value=0)
    return (
        conteo.rename_axis("hora")
        .reset_index(name="n_episodios")
        .astype({"hora": int, "n_episodios": int})
        .sort_values("hora")
        .reset_index(drop=True)
    )


def ciclo_estacional(
    df: pd.DataFrame, umbral: float = UMBRAL_EMERGENCIA_UG_M3, parametro: str = SO2_HORARIO
) -> pd.DataFrame:
    """En qué mes (1-12) caen las horas >= `umbral`. Ver `ciclo_horario`."""
    sub = df[(df["parametro"] == parametro) & (df["valor"] >= umbral)]
    conteo = sub["fecha_hora"].dt.month.value_counts().reindex(range(1, 13), fill_value=0)
    return (
        conteo.rename_axis("mes")
        .reset_index(name="n_episodios")
        .astype({"mes": int, "n_episodios": int})
        .sort_values("mes")
        .reset_index(drop=True)
    )


def reconstruccion_diaria(
    df: pd.DataFrame,
    estacion: str = ESTACION_RECONSTRUCCION,
    tolerancia: float = TOLERANCIA_RECONSTRUCCION_UG_M3,
) -> dict:
    """LA VERIFICACIÓN CENTRAL (CLAUDE.md §8.3).

    Promedia la serie horaria de `estacion` a diaria y la compara contra la
    serie `so2_diario` ya consolidada en `df`. Debe coincidir en ~99,9 % de
    9.427 días con diferencia mediana 0,000: si el resultado no se acerca a
    eso, significa que la ingesta está mal -- no son el mismo dato a dos
    resoluciones -- y hay que parar ahí.
    """
    horaria = df[(df["estacion"] == estacion) & (df["parametro"] == SO2_HORARIO)].copy()
    horaria["fecha"] = horaria["fecha_hora"].dt.floor("D")
    reconstruida = horaria.groupby("fecha")["valor"].mean()

    diaria = df[(df["estacion"] == estacion) & (df["parametro"] == SO2_DIARIO)]
    diaria = diaria.dropna(subset=["valor"]).copy()
    reportada = pd.Series(diaria["valor"].to_numpy(), index=diaria["fecha_hora"].dt.floor("D"))

    comparado = pd.DataFrame({"reportada": reportada, "reconstruida": reconstruida}).dropna()
    diferencia = (comparado["reportada"] - comparado["reconstruida"]).abs()

    n = len(comparado)
    n_coincide = int((diferencia <= tolerancia).sum())

    return {
        "estacion": estacion,
        "n_dias_comparados": n,
        "tolerancia_ug_m3": tolerancia,
        "n_dias_coincide": n_coincide,
        "pct_coincide": float(n_coincide / n * 100) if n else 0.0,
        "diferencia_mediana_ug_m3": float(diferencia.median()) if n else float("nan"),
        "diferencia_media_ug_m3": float(diferencia.mean()) if n else float("nan"),
        "diferencia_maxima_ug_m3": float(diferencia.max()) if n else float("nan"),
    }


def comparacion_resolucion(
    df: pd.DataFrame,
    estacion: str = ESTACION_RECONSTRUCCION,
    umbral_diario: float = UMBRAL_NORMA_DIARIA_UG_M3,
    umbral_emergencia: float = UMBRAL_EMERGENCIA_UG_M3,
) -> dict:
    """LA DEMOSTRACIÓN (CLAUDE.md §8.3): misma estación, mismo periodo, dos
    resoluciones.

    Cuenta cuántas superaciones de la norma de 24 h (150 µg/m³) hay en la
    serie diaria publicada, frente a cuántas horas de emergencia (>=500
    µg/m³) hay en la serie horaria de la misma estación.
    """
    diaria = df[(df["estacion"] == estacion) & (df["parametro"] == SO2_DIARIO)]
    diaria = diaria.dropna(subset=["valor"])
    horaria = df[(df["estacion"] == estacion) & (df["parametro"] == SO2_HORARIO)]
    horaria = horaria.dropna(subset=["valor"])

    superaciones_diarias = diaria[diaria["valor"] >= umbral_diario].copy()
    superaciones_diarias["anio"] = superaciones_diarias["fecha_hora"].dt.year

    return {
        "estacion": estacion,
        "periodo_diario": [
            str(diaria["fecha_hora"].min().date()),
            str(diaria["fecha_hora"].max().date()),
        ],
        "n_dias_diarios": len(diaria),
        "umbral_diario_ug_m3": umbral_diario,
        "superaciones_diarias": len(superaciones_diarias),
        "superaciones_diarias_desde_2019": int((superaciones_diarias["anio"] >= 2019).sum()),
        "maximo_diario_ug_m3": float(diaria["valor"].max()),
        "periodo_horario": [
            str(horaria["fecha_hora"].min().date()),
            str(horaria["fecha_hora"].max().date()),
        ],
        "n_horas_horarias": len(horaria),
        "umbral_emergencia_ug_m3": umbral_emergencia,
        "horas_emergencia": int((horaria["valor"] >= umbral_emergencia).sum()),
    }
