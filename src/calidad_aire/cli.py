"""Interfaz de línea de comandos del proyecto (`caq`)."""

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import typer

from calidad_aire import eda as eda_mod
from calidad_aire import figures
from calidad_aire.data import load_validated
from calidad_aire.ingest import consolidar

app = typer.Typer(help="Calidad del aire en Quintero-Puchuncaví.")

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PARQUET_PATH = PROCESSED_DIR / "sinca.parquet"
QUARANTINE_DIR = Path("data/quarantine")
REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"

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
    descartadas = len(crudo) - len(validas) - len(cuarentena)
    typer.echo(
        f"  {len(validas):,} filas válidas, {len(cuarentena):,} en cuarentena, "
        f"{descartadas:,} descartadas en silencio (sin valor, anteriores al "
        "inicio de operación de su estación -- CLAUDE.md §8.6.4)."
    )

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


@app.command()
def eda() -> None:
    """Análisis exploratorio: reports/eda.json y reports/figures/ (CLAUDE.md §8.3)."""
    typer.echo(f"Leyendo {PARQUET_PATH} ...")
    df = pd.read_parquet(PARQUET_PATH)
    so2 = df[df["parametro"].isin(["so2_horario", "so2_diario"])].copy()
    nucleo = so2[so2["estacion"].isin(figures.ESTACIONES_NUCLEO)]

    typer.echo("Calculando cobertura, episodios y ciclos ...")
    cobertura = eda_mod.cobertura_por_estacion_y_anio(so2)
    episodios_350 = eda_mod.episodios(so2, umbral=350)
    episodios_500 = eda_mod.episodios(so2, umbral=500)
    resumen = eda_mod.resumen_anual(so2)
    ciclo_horario = eda_mod.ciclo_horario(nucleo)
    ciclo_estacional = eda_mod.ciclo_estacional(nucleo)

    typer.echo("Verificando la reconstrucción diaria (la comprobación central) ...")
    reconstruccion = eda_mod.reconstruccion_diaria(so2)
    typer.echo(
        f"  {reconstruccion['n_dias_comparados']} días comparados, diferencia mediana "
        f"{reconstruccion['diferencia_mediana_ug_m3']:.2e} µg/m³ -- distribución "
        "(sin criterio de aprobado/reprobado, CLAUDE.md §8.3):"
    )
    for fila in reconstruccion["distribucion"]:
        typer.echo(
            f"    tolerancia {fila['tolerancia_ug_m3']} -> {fila['pct_coincide']:.3f}% "
            f"({fila['n_dias_fuera']} días fuera)"
        )
    n_discrepantes = len(reconstruccion["dias_discrepantes"])
    if n_discrepantes:
        typer.echo(
            f"  {n_discrepantes} días exceden "
            f"{reconstruccion['umbral_dia_discrepante_ug_m3']} µg/m³ de diferencia "
            "(ver reports/eda.json -- todos con cobertura horaria casi completa: no es un "
            "problema de huecos)."
        )

    comparacion = eda_mod.comparacion_resolucion(so2)
    typer.echo(
        f"  serie diaria: {comparacion['superaciones_diarias']} superaciones de "
        f"{comparacion['umbral_diario_ug_m3']} µg/m³ en {comparacion['n_dias_diarios']} días -- "
        f"serie horaria: {comparacion['horas_emergencia']} horas de emergencia en "
        f"{comparacion['n_horas_horarias']} horas."
    )

    ventanas_falla = eda_mod.ventanas_falla_sensor(df)
    for fila in ventanas_falla:
        typer.echo(
            f"  ventana de falla de sensor: {fila['estacion']}/{fila['parametro']} "
            f"{fila['inicio']} a {fila['fin']} -- {fila['n_horas']} horas, "
            f"{fila['n_horas_con_valor']} con valor (debería ser 0, ver CLAUDE.md §8.6.5)."
        )

    informe = {
        "generado_en": dt.datetime.now().isoformat(timespec="seconds"),
        "cobertura_por_estacion_y_anio": eda_mod.registros(cobertura),
        "episodios_350": eda_mod.registros(episodios_350),
        "episodios_500": eda_mod.registros(episodios_500),
        "resumen_anual": eda_mod.registros(resumen),
        "ciclo_horario_500": eda_mod.registros(ciclo_horario),
        "ciclo_estacional_500": eda_mod.registros(ciclo_estacional),
        "reconstruccion_diaria": reconstruccion,
        "comparacion_resolucion": comparacion,
        "ventanas_falla_sensor": ventanas_falla,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    informe_path = REPORTS_DIR / "eda.json"
    informe_path.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"Escrito {informe_path}.")

    typer.echo(f"Dibujando figuras en {FIGURES_DIR} ...")
    figures.figura_serie_anual_emergencias(
        episodios_500, FIGURES_DIR / "serie_anual_emergencias.png"
    )
    figures.figura_maximo_anual(resumen, FIGURES_DIR / "maximo_anual.png")
    figures.figura_clave_resolucion(so2, FIGURES_DIR / "resolucion_clave.png")
    figures.figura_mapa_calor_ciclo(so2, FIGURES_DIR / "mapa_calor_episodios.png")
    figures.figura_cobertura(cobertura, FIGURES_DIR / "cobertura_datos.png")
    typer.echo("Listo.")


if __name__ == "__main__":
    app()
