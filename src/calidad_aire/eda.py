"""Análisis exploratorio y la demostración de que el dato público diario no
puede mostrar los episodios (CLAUDE.md §8.3).

Funciones puras: reciben el `DataFrame` consolidado (columnas `estacion`,
`parametro`, `fecha_hora`, `valor`, `estado`) y devuelven `DataFrame`/`dict`,
sin leer ni escribir ficheros -- eso vive en `cli.py`.

`reconstruccion_diaria` es LA VERIFICACIÓN CENTRAL de esta fase (CLAUDE.md
§8.3): compara la reconstrucción horaria->diaria contra la serie diaria
publicada. No devuelve un aprobado/reprobado contra una tolerancia: la
tolerancia "correcta" no existe -- siete de 9.427 días difieren en más de 1
µg/m³ con las 24 horas completas, una discrepancia real entre dos productos
de SINCA sobre el mismo dato, no un problema de cobertura. La función
devuelve la distribución completa (varios niveles de tolerancia) y la lista
de esos días exactos, para que quien lea el reporte juzgue por sí mismo.
"""

from __future__ import annotations

import pandas as pd

from calidad_aire.schema import VENTANAS_FALLA_SENSOR

SO2_HORARIO = "so2_horario"
SO2_DIARIO = "so2_diario"

UMBRAL_NORMA_HORARIA_UG_M3 = 350
UMBRAL_NORMA_DIARIA_UG_M3 = 150
UMBRAL_EMERGENCIA_UG_M3 = 500

ESTACION_RECONSTRUCCION = "los_maitenes"

# Niveles de tolerancia que se reportan en la distribución, y el umbral por
# encima del cual un día se lista individualmente en "dias_discrepantes".
# No hay un criterio de aprobado/reprobado (ver docstring del módulo).
NIVELES_TOLERANCIA_UG_M3 = (0.1, 0.5, 1.0, 2.0, 5.0)
UMBRAL_DIA_DISCREPANTE_UG_M3 = 1.0


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
    niveles_tolerancia: tuple[float, ...] = NIVELES_TOLERANCIA_UG_M3,
    umbral_dia_discrepante: float = UMBRAL_DIA_DISCREPANTE_UG_M3,
) -> dict:
    """LA VERIFICACIÓN CENTRAL (CLAUDE.md §8.3). Ver docstring del módulo.

    Promedia la serie horaria de `estacion` a diaria y la compara contra la
    serie `so2_diario` ya consolidada en `df`, día por día. Devuelve la
    distribución completa de la diferencia absoluta a varios niveles de
    tolerancia, y la lista de los días que exceden `umbral_dia_discrepante`
    con su diferencia y su número de horas válidas ese día -- para
    comprobar, como aquí, que no son días de baja cobertura.
    """
    horaria = df[(df["estacion"] == estacion) & (df["parametro"] == SO2_HORARIO)].copy()
    horaria["fecha"] = horaria["fecha_hora"].dt.floor("D")
    por_fecha = horaria.groupby("fecha")["valor"]
    reconstruida = por_fecha.mean()
    n_horas = por_fecha.apply(lambda s: int(s.notna().sum()))

    diaria = df[(df["estacion"] == estacion) & (df["parametro"] == SO2_DIARIO)]
    diaria = diaria.dropna(subset=["valor"]).copy()
    reportada = pd.Series(diaria["valor"].to_numpy(), index=diaria["fecha_hora"].dt.floor("D"))

    comparado = pd.DataFrame(
        {"reportada": reportada, "reconstruida": reconstruida, "n_horas": n_horas}
    ).dropna(subset=["reportada", "reconstruida"])
    diferencia = (comparado["reportada"] - comparado["reconstruida"]).abs()

    n = len(comparado)
    distribucion = [
        {
            "tolerancia_ug_m3": tolerancia,
            "pct_coincide": float((diferencia <= tolerancia).mean() * 100) if n else 0.0,
            "n_dias_fuera": int((diferencia > tolerancia).sum()),
        }
        for tolerancia in niveles_tolerancia
    ]

    discrepantes = comparado.loc[diferencia > umbral_dia_discrepante].copy()
    discrepantes["diferencia_ug_m3"] = diferencia.loc[discrepantes.index]
    discrepantes = discrepantes.sort_values("diferencia_ug_m3", ascending=False)
    dias_discrepantes = [
        {
            "fecha": str(fecha.date()),
            "diferencia_ug_m3": float(fila["diferencia_ug_m3"]),
            "n_horas": int(fila["n_horas"]),
        }
        for fecha, fila in discrepantes.iterrows()
    ]

    return {
        "estacion": estacion,
        "n_dias_comparados": n,
        "diferencia_mediana_ug_m3": float(diferencia.median()) if n else float("nan"),
        "diferencia_media_ug_m3": float(diferencia.mean()) if n else float("nan"),
        "diferencia_maxima_ug_m3": float(diferencia.max()) if n else float("nan"),
        "distribucion": distribucion,
        "umbral_dia_discrepante_ug_m3": umbral_dia_discrepante,
        "dias_discrepantes": dias_discrepantes,
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


def ventanas_falla_sensor(df: pd.DataFrame) -> list[dict]:
    """Expone `schema.VENTANAS_FALLA_SENSOR` con sus horas medidas en `df`,
    para que la fase 3 la lea del informe en vez de redescubrirla
    (CLAUDE.md §8.6.5 y §9.1: son huecos que hay que tratar explícitamente,
    no interpolar por encima).

    Tras el contrato, toda hora con valor dentro de la ventana ya fue a
    cuarentena: `n_horas_con_valor` debería dar 0 sobre un `df` que ya pasó
    por `data.load_validated` (el parquet). Si no da 0, algo se está
    imputando o coló un valor que el contrato debería haber rechazado.
    """
    filas = []
    for estacion, parametro, inicio, fin in VENTANAS_FALLA_SENSOR:
        tramo = df[
            (df["estacion"] == estacion)
            & (df["parametro"] == parametro)
            & (df["fecha_hora"] >= inicio)
            & (df["fecha_hora"] <= fin)
        ]
        filas.append(
            {
                "estacion": estacion,
                "parametro": parametro,
                "inicio": str(inicio),
                "fin": str(fin),
                "n_horas": len(tramo),
                "n_horas_con_valor": int(tramo["valor"].notna().sum()),
            }
        )
    return filas
