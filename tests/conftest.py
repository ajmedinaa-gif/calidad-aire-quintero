from pathlib import Path

import pandas as pd
import pytest

RAW_DIR = Path("data/raw")

requiere_datos_crudos = pytest.mark.skipif(
    not RAW_DIR.exists(),
    reason="data/raw no está versionado (CLAUDE.md §11); clonar y descargar de sinca.mma.gob.cl.",
)


@pytest.fixture(scope="session")
def tabla_consolidada() -> pd.DataFrame:
    from calidad_aire.ingest import consolidar

    return consolidar(RAW_DIR)
