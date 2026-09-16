"""Ingesta de exportaciones horarias/diarias de SINCA a una tabla larga.

Formato SINCA (CLAUDE.md §8): separador `;`, decimal con coma, codificación
latin-1, fecha `YYMMDD` (YY < 50 -> 20YY, si no 19YY) y hora `HHMM`.

Se han observado dos variantes de columnas entre los parámetros de esta
descarga:

- Parámetros de concentración (SO2, NO2, O3, MP10, MP25, CO): tres columnas de
  estado -- "Registros validados", "Registros preliminares",
  "Registros no validados" -- de las que el valor aparece en como máximo una.
- Dirección y velocidad de viento: una única columna de valor, sin desglose
  de estado. SINCA no ofrece para estos parámetros la misma clasificación de
  acreditación que para los de concentración, así que se etiquetan como
  "no_validado" cuando hay valor: es un dato entregado pero sin certificar,
  la lectura más conservadora del contrato de CLAUDE.md §8.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

CABECERA_ESPERADA_PREFIJO = ("FECHA (YYMMDD)", "HORA (HHMM)")


class FormatoSincaError(ValueError):
    """El fichero no tiene el formato de una serie SINCA por registro."""


def parse_fecha_hora(fecha: str, hora: str) -> datetime:
    """Convierte fecha `YYMMDD` y hora `HHMM` de SINCA a `datetime`.

    Regla del siglo: YY < 50 -> 20YY, si no 19YY. Hay datos desde 1970 y hasta
    2026 en esta descarga, así que la regla importa de verdad (CLAUDE.md §8.6).
    """
    fecha = fecha.strip()
    hora = hora.strip().zfill(4)

    yy = int(fecha[0:2])
    mes = int(fecha[2:4])
    dia = int(fecha[4:6])
    anio = 2000 + yy if yy < 50 else 1900 + yy

    hh = int(hora[0:2])
    mm = int(hora[2:4])

    return datetime(anio, mes, dia, hh, mm)


def _parse_fecha_hora_serie(fecha: pd.Series, hora: pd.Series) -> pd.Series:
    """Versión vectorizada de `parse_fecha_hora` para columnas completas.

    Misma regla del siglo; se usa dentro de `leer_sinca` porque construir un
    `datetime` por fila en Python es demasiado lento sobre millones de filas.
    """
    yy = fecha.str[0:2].astype(int)
    anio = yy.where(yy >= 50, yy + 100) + 1900
    mes = fecha.str[2:4].astype(int)
    dia = fecha.str[4:6].astype(int)

    hora4 = hora.str.zfill(4)
    hh = hora4.str[0:2].astype(int)
    mm = hora4.str[2:4].astype(int)

    return pd.to_datetime({"year": anio, "month": mes, "day": dia, "hour": hh, "minute": mm})


def _es_cabecera_serie_sinca(primera_linea: str) -> bool:
    campos = primera_linea.split(";")
    if len(campos) < 2:
        return False
    return (
        campos[0].strip() == CABECERA_ESPERADA_PREFIJO[0]
        and campos[1].strip() == (CABECERA_ESPERADA_PREFIJO[1])
    )


def leer_sinca(path: Path | str) -> pd.DataFrame:
    """Lee un CSV crudo de SINCA y devuelve columnas `fecha_hora, valor, estado`.

    Lanza `FormatoSincaError` con un mensaje claro si el fichero no es una
    serie por registro (por ejemplo, una tabla resumen de rosa de vientos),
    en vez de fallar con un stack trace de pandas.
    """
    path = Path(path)
    with path.open(encoding="latin-1") as fh:
        primera_linea = fh.readline()

    if not primera_linea:
        raise FormatoSincaError(f"{path}: fichero vacío.")
    if not _es_cabecera_serie_sinca(primera_linea):
        raise FormatoSincaError(
            f"{path}: la cabecera no empieza con 'FECHA (YYMMDD);HORA (HHMM)'. "
            "Probablemente es una tabla resumen (p.ej. rosa de vientos) y no una "
            "serie por registro; este fichero no se puede consolidar tal cual."
        )

    n_columnas = len(primera_linea.rstrip("\n").split(";"))

    crudo = pd.read_csv(
        path,
        sep=";",
        encoding="latin-1",
        header=0,
        dtype=str,
        keep_default_na=False,
    )

    fecha_hora = _parse_fecha_hora_serie(crudo.iloc[:, 0], crudo.iloc[:, 1])

    if n_columnas >= 5:
        # Formato con tres columnas de estado (parámetros de concentración).
        validado = pd.to_numeric(crudo.iloc[:, 2].str.replace(",", "."), errors="coerce")
        preliminar = pd.to_numeric(crudo.iloc[:, 3].str.replace(",", "."), errors="coerce")
        no_validado = pd.to_numeric(crudo.iloc[:, 4].str.replace(",", "."), errors="coerce")

        valor = validado.combine_first(preliminar).combine_first(no_validado)
        estado = pd.Series("ausente", index=crudo.index, dtype=object)
        estado[validado.notna()] = "validado"
        estado[preliminar.notna() & validado.isna()] = "preliminar"
        estado[no_validado.notna() & validado.isna() & preliminar.isna()] = "no_validado"
    else:
        # Formato de una sola columna de valor (dirección/velocidad de viento):
        # sin desglose de estado en la fuente, se etiqueta "no_validado" cuando
        # hay valor (ver docstring del módulo).
        valor = pd.to_numeric(crudo.iloc[:, 2].str.replace(",", "."), errors="coerce")
        estado = pd.Series("ausente", index=crudo.index, dtype=object)
        estado[valor.notna()] = "no_validado"

    return pd.DataFrame({"fecha_hora": fecha_hora, "valor": valor.to_numpy(), "estado": estado})


@dataclass(frozen=True)
class FicheroSinca:
    estacion: str
    parametro: str
    path: Path


def _listar_ficheros(raw_dir: Path) -> list[FicheroSinca]:
    ficheros = []
    for estacion_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        for csv_path in sorted(estacion_dir.glob("*.csv")):
            ficheros.append(
                FicheroSinca(estacion=estacion_dir.name, parametro=csv_path.stem, path=csv_path)
            )
    return ficheros


def consolidar(raw_dir: Path | str = "data/raw") -> pd.DataFrame:
    """Recorre `data/raw/<estacion>/<parametro>.csv` y arma la tabla larga.

    El nombre del fichero (sin extensión) es la fuente de verdad del
    `parametro`, incluida la resolución temporal (p.ej. `so2_horario` frente a
    `so2_diario`): son series distintas y no deben mezclarse bajo la misma
    clave estacion+parametro+fecha_hora.
    """
    raw_dir = Path(raw_dir)
    tablas = []
    for fichero in _listar_ficheros(raw_dir):
        tabla = leer_sinca(fichero.path)
        tabla.insert(0, "parametro", fichero.parametro)
        tabla.insert(0, "estacion", fichero.estacion)
        tablas.append(tabla)

    if not tablas:
        raise FormatoSincaError(f"No se encontraron CSV en {raw_dir}.")

    return pd.concat(tablas, ignore_index=True)
