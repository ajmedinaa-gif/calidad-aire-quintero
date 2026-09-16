from pathlib import Path

import pandas as pd
import pytest

RAW_DIR = Path("data/raw")
PARQUET_PATH = Path("data/processed/sinca.parquet")

requiere_datos_crudos = pytest.mark.skipif(
    not RAW_DIR.exists(),
    reason="data/raw no está versionado (CLAUDE.md §11); clonar y descargar de sinca.mma.gob.cl.",
)

requiere_datos_procesados = pytest.mark.skipif(
    not PARQUET_PATH.exists(),
    reason="data/processed/sinca.parquet no existe; ejecutar `make ingest` primero.",
)


@pytest.fixture(scope="session")
def tabla_consolidada() -> pd.DataFrame:
    from calidad_aire.ingest import consolidar

    return consolidar(RAW_DIR)


@pytest.fixture(scope="session")
def tabla_procesada() -> pd.DataFrame:
    return pd.read_parquet(PARQUET_PATH)
