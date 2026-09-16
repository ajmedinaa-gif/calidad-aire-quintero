"""Aplica el contrato de `schema.py`: separa filas válidas de las de cuarentena.

Regla dura 4 de CLAUDE.md: los datos que no pasan el contrato van a
`data/quarantine/`, con el motivo. No se borran ni se imputan en silencio.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from calidad_aire.schema import ESQUEMA_SINCA

QUARANTINE_DIR = Path("data/quarantine")


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
    """
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
