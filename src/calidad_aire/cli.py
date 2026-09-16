"""Interfaz de línea de comandos del proyecto (`caq`)."""

from pathlib import Path

import typer

from calidad_aire.data import load_validated
from calidad_aire.ingest import consolidar

app = typer.Typer(help="Calidad del aire en Quintero-Puchuncaví.")

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PARQUET_PATH = PROCESSED_DIR / "sinca.parquet"
QUARANTINE_DIR = Path("data/quarantine")

# CLAUDE.md §11: sinca.parquet se versiona solo si pesa menos de 25 MB. Con
# los 11 parámetros completos pesa 56 MB (34 MB incluso con category+zstd-19);
# con SO2 y viento (el núcleo de las fases 2-4: recuperación y pronóstico)
# pesa ~20 MB. Se decide persistir solo esos parámetros; NO2, O3, MP10, MP25
# y CO quedan validados pero no persistidos -- se recuperan re-ejecutando
# `caq ingest` sobre data/raw/.
PARAMETROS_A_VERSIONAR = ("so2_", "direccion_viento", "velocidad_viento")

# zstd nivel 15 comprime mejor que gzip para esta tabla (columnas category ya
# son minúsculas; fecha_hora y valor dominan el peso): 19.6 MB frente a los
# 21.6 MB de gzip por defecto, medido sobre los datos reales.
COMPRESION_PARQUET = "zstd"
NIVEL_COMPRESION_PARQUET = 15


@app.command()
def version() -> None:
    """Muestra la versión instalada del paquete."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("calidad-aire-quintero"))


@app.command()
def ingest() -> None:
    """Consolida `data/raw/` en un parquet validado, con cuarentena aparte."""
    typer.echo(f"Consolidando CSV de SINCA desde {RAW_DIR} ...")
    crudo = consolidar(RAW_DIR)
    typer.echo(f"  {len(crudo):,} filas leídas en {crudo['estacion'].nunique()} estaciones.")

    typer.echo("Validando contra el contrato de datos ...")
    validas, cuarentena = load_validated(crudo, quarantine_dir=QUARANTINE_DIR)
    typer.echo(f"  {len(validas):,} filas válidas, {len(cuarentena):,} en cuarentena.")

    a_versionar = validas[validas["parametro"].str.startswith(PARAMETROS_A_VERSIONAR)].copy()
    a_versionar["estacion"] = a_versionar["estacion"].astype("category")
    a_versionar["parametro"] = a_versionar["parametro"].astype("category")
    a_versionar["estado"] = a_versionar["estado"].astype("category")
    a_versionar["valor"] = a_versionar["valor"].astype("float32")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    a_versionar.to_parquet(
        PARQUET_PATH,
        index=False,
        compression=COMPRESION_PARQUET,
        compression_level=NIVEL_COMPRESION_PARQUET,
    )
    tamano_mb = PARQUET_PATH.stat().st_size / (1024 * 1024)
    typer.echo(f"Escrito {PARQUET_PATH} ({tamano_mb:.2f} MB, solo SO2 y viento -- CLAUDE.md §11).")
    if tamano_mb > 25:
        typer.echo("AVISO: sigue superando 25 MB. Revisar antes de hacer commit.")

    if not cuarentena.empty:
        typer.echo(f"Motivos en cuarentena:\n{cuarentena['motivo'].value_counts().to_string()}")


if __name__ == "__main__":
    app()
