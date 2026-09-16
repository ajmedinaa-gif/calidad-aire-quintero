"""Aplica el contrato de `schema.py`: separa filas válidas de las de cuarentena.

Regla dura 4 de CLAUDE.md: los datos que no pasan el contrato van a
`data/quarantine/`, con el motivo. No se borran ni se imputan en silencio.

Excepción deliberada (CLAUDE.md §8.6.4, paso 4): una fila SIN valor, fechada
antes de que su estación empezara a operar, no lleva ninguna información --
es una fila vacía que SINCA rellena por continuidad del rango de fechas del
export, no un dato perdido. Ingerirla como válida sería incorrecto (nunca
hubo estación ahí) y mandarla a cuarentena sería ruido puro: solo en
la_greda/velocidad_viento_horario son ~350.000 filas de nada. Por eso se
descarta antes de validar, en silencio. Una fila CON valor en ese mismo
rango es harina de otro costal -- sí es un dato, y si es anterior a la
operación, el contrato la rechaza y SÍ queda documentada en cuarentena con
motivo "fecha_anterior_a_operacion".
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from calidad_aire.schema import ESQUEMA_SINCA, INICIO_OPERACION, validar_claves_conocidas

QUARANTINE_DIR = Path("data/quarantine")


def _antes_de_operacion(df: pd.DataFrame) -> pd.Series:
    inicio = pd.Series(
        [
            INICIO_OPERACION.get(clave)
            for clave in zip(df["estacion"], df["parametro"], strict=True)
        ],
        index=df.index,
    )
    return inicio.notna() & (df["fecha_hora"] < inicio)


def descartar_ausentes_antes_de_operacion(df: pd.DataFrame) -> pd.DataFrame:
    """Quita, antes de validar, las filas sin valor anteriores al inicio de
    operación de su (estación, parámetro). Ver docstring del módulo.
    """
    sin_valor_antes = _antes_de_operacion(df) & df["valor"].isna()
    return df.loc[~sin_valor_antes].copy()


def _motivos_por_fila(failure_cases: pd.DataFrame) -> pd.Series:
    """Colapsa `failure_cases` de pandera a un motivo por índice de fila."""
    con_indice = failure_cases.dropna(subset=["index"])
    motivos = con_indice.groupby("index")["check"].apply(lambda s: "; ".join(sorted(set(s))))
    motivos.index = motivos.index.astype(int)
    return motivos


def load_validated(
    df: pd.DataFrame, quarantine_dir: Path | str = QUARANTINE_DIR
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valida `df` contra `ESQUEMA_SINCA` y separa lo válido de lo cuarentenado.

    Devuelve `(validas, cuarentena)`. `cuarentena` trae todas las columnas de
    `df` más `motivo`. Si hay filas en cuarentena, además se escriben a
    `<quarantine_dir>/<timestamp>.csv`.

    Antes de validar, descarta en silencio las filas sin valor anteriores al
    inicio de operación de su estación (`descartar_ausentes_antes_de_operacion`,
    ver docstring del módulo): por eso `len(validas) + len(cuarentena)` puede
    ser menor que `len(df)`.
    """
    validar_claves_conocidas(df)
    df = descartar_ausentes_antes_de_operacion(df)
    try:
        ESQUEMA_SINCA.validate(df, lazy=True)
        return df, df.iloc[0:0].copy().assign(motivo=pd.Series(dtype=str))
    except pa.errors.SchemaErrors as err:
        motivos = _motivos_por_fila(err.failure_cases)

        indices_invalidos = pd.Index(motivos.index)
        cuarentena = df.loc[df.index.isin(indices_invalidos)].copy()
        cuarentena["motivo"] = cuarentena.index.map(motivos)

        validas = df.loc[~df.index.isin(indices_invalidos)].copy()

        if not cuarentena.empty:
            _escribir_cuarentena(cuarentena, quarantine_dir)

        return validas, cuarentena


def _escribir_cuarentena(cuarentena: pd.DataFrame, quarantine_dir: Path | str) -> Path:
    quarantine_dir = Path(quarantine_dir)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    destino = quarantine_dir / f"{timestamp}.csv"
    cuarentena.to_csv(destino, index=False)
    return destino
