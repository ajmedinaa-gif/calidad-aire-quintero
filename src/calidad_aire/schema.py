"""Contrato de datos de la tabla larga consolidada (CLAUDE.md, regla dura 4).

Rangos físicos por parámetro:

- Concentración (so2, no2, o3, mp10, mp25, co, ...): valor >= 0.
- direccion_viento: 0 a 360 grados.
- velocidad_viento: 0 a 60 m/s (el récord mundial ronda los 113 m/s; 60 es
  generoso y deja fuera el imposible físico conocido de esta descarga).
- fecha_hora: entre 1970-01-01 y hoy.

El `parametro` incluye la resolución en el nombre (p.ej. `so2_horario`,
`so2_diario`); el límite físico depende solo de la magnitud, así que se
compara contra el nombre sin el sufijo `_horario`/`_diario`.

CO no aparece en el inventario de CLAUDE.md §8.1, pero existe en la descarga
de `las_palmas`: se trata como concentración (valor >= 0), la lectura más
razonable dado que es, como los demás, un contaminante gaseoso.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pandera.pandas as pa

VELOCIDAD_VIENTO_MAX_M_S = 60
DIRECCION_VIENTO_MIN_DEG = 0
DIRECCION_VIENTO_MAX_DEG = 360
FECHA_MINIMA = pd.Timestamp("1970-01-01")

ESTADOS_VALIDOS = ("validado", "preliminar", "no_validado", "ausente")

_SUFIJO_RESOLUCION = r"_(horario|diario)$"


def _parametro_base(parametro: pd.Series) -> pd.Series:
    return parametro.str.replace(_SUFIJO_RESOLUCION, "", regex=True)


def valor_en_rango_fisico(df: pd.DataFrame) -> pd.Series:
    """True donde `valor` respeta el rango físico de su parámetro, o es nulo."""
    base = _parametro_base(df["parametro"])
    valor = df["valor"]

    ok = pd.Series(True, index=df.index)

    es_direccion = base == "direccion_viento"
    ok.loc[es_direccion] = valor.loc[es_direccion].between(
        DIRECCION_VIENTO_MIN_DEG, DIRECCION_VIENTO_MAX_DEG
    )

    es_velocidad = base == "velocidad_viento"
    ok.loc[es_velocidad] = valor.loc[es_velocidad].between(0, VELOCIDAD_VIENTO_MAX_M_S)

    es_concentracion = ~es_direccion & ~es_velocidad
    ok.loc[es_concentracion] = valor.loc[es_concentracion] >= 0

    ok.loc[valor.isna()] = True
    return ok


def fecha_hora_en_rango(df: pd.DataFrame) -> pd.Series:
    """True donde `fecha_hora` está entre 1970-01-01 y hoy."""
    hoy = pd.Timestamp(dt.date.today()) + pd.Timedelta(days=1)
    return df["fecha_hora"].between(FECHA_MINIMA, hoy)


ESQUEMA_SINCA = pa.DataFrameSchema(
    columns={
        "estacion": pa.Column(str),
        "parametro": pa.Column(str),
        "fecha_hora": pa.Column("datetime64[ns]"),
        "valor": pa.Column(float, nullable=True),
        "estado": pa.Column(str, checks=pa.Check.isin(ESTADOS_VALIDOS)),
    },
    checks=[
        pa.Check(valor_en_rango_fisico, error="valor fuera de rango físico"),
        pa.Check(fecha_hora_en_rango, error="fecha_hora fuera de 1970-01-01..hoy"),
    ],
    strict=False,
    coerce=False,
)
