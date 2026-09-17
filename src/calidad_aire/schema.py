"""Contrato de datos de la tabla larga consolidada (CLAUDE.md, regla dura 4).

Rangos físicos por parámetro:

- Concentración (so2, no2, o3, mp10, mp25, co, ...): valor >= 0.
- direccion_viento: 0 a 360 grados.
- velocidad_viento: 0 a 60 m/s (el récord mundial ronda los 113 m/s; 60 es
  generoso y deja fuera el imposible físico conocido de esta descarga).
- fecha_hora: entre el inicio de operación de esa (estación, parámetro) y hoy.

El `parametro` incluye la resolución en el nombre (p.ej. `so2_horario`,
`so2_diario`); el límite físico depende solo de la magnitud, así que se
compara contra el nombre sin el sufijo `_horario`/`_diario`.

CO no aparece en el inventario de CLAUDE.md §8.1, pero existe en la descarga
de `las_palmas`: se trata como concentración (valor >= 0), la lectura más
razonable dado que es, como los demás, un contaminante gaseoso.

Sobre el límite inferior de fecha (CLAUDE.md §8.6.4): un `FECHA_MINIMA`
global fijado en el epoch de Unix (1970-01-01) no puede rechazar nada, porque
es exactamente el valor que produce una exportación de SINCA rota. Se
sustituyó por `INICIO_OPERACION`, una tabla explícita medida a mano.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pandera.pandas as pa

VELOCIDAD_VIENTO_MAX_M_S = 60
DIRECCION_VIENTO_MIN_DEG = 0
DIRECCION_VIENTO_MAX_DEG = 360

ESTADOS_VALIDOS = ("validado", "preliminar", "no_validado", "ausente")

_SUFIJO_RESOLUCION = r"_(horario|diario)$"

# Inicio de operación real de cada (estación, parámetro): para 29 de los 32
# pares es, sin más, la primera fecha_hora con un valor no nulo en el CSV
# crudo (medido el 2026-09-16 consolidando los 5.910.595 registros de
# data/raw/ y agrupando por año -- ver CLAUDE.md §8.6.4).
#
# Los otros 3 pares NO usan esa regla, porque tienen valores no nulos
# anteriores a su arranque real que son basura numérica de la propia fuente,
# no datos -- verificado inspeccionando esas filas una por una, no asumido
# por la cobertura sola:
#   - la_greda/direccion_viento_horario y la_greda/velocidad_viento_horario:
#     entre 1970 y 2009 hay apenas 32 y 58 lecturas respectivamente en 40
#     años, con valores como -72,0026 grados o 5,8155e+35 m/s. El bloque
#     real y sostenido (95,6 % de cobertura) empieza en 2010.
#   - puchuncavi/no2_horario: 63 lecturas en 1986, del orden de 5e-7 µg/m³
#     -- indistinguible de ruido de piso de instrumento, no de una medición.
#     Los datos reales (2,7 a 28,8 µg/m³) empiezan el 2009-08-31.
# Sin esta distinción, la tabla habría desplazado el inicio de operación de
# la_greda/so2_horario o las_palmas/so2_horario también, borrando datos de
# SO2 reales y perfectamente plausibles solo por tener baja cobertura en su
# primer año (p.ej. las_palmas/so2_horario cae a 15,6 % en el año 2000, y
# sigue siendo SO2 real, no basura). SO2 no tiene ninguna excepción: los
# cuatro pares de SO2 usan su primera fecha con dato, sin recortes.
INICIO_OPERACION: dict[tuple[str, str], pd.Timestamp] = {
    ("la_greda", "so2_horario"): pd.Timestamp("1993-01-01"),
    ("la_greda", "no2_horario"): pd.Timestamp("2009-09-01"),
    ("la_greda", "o3_horario"): pd.Timestamp("2010-01-30"),
    ("la_greda", "mp25_horario"): pd.Timestamp("2012-07-29"),
    ("la_greda", "direccion_viento_horario"): pd.Timestamp("2010-01-01"),  # excepción, ver arriba
    ("la_greda", "velocidad_viento_horario"): pd.Timestamp("2010-01-01"),  # excepción, ver arriba
    ("las_palmas", "so2_horario"): pd.Timestamp("1999-02-06"),
    ("las_palmas", "o3_horario"): pd.Timestamp("1999-02-06"),
    ("las_palmas", "velocidad_viento_horario"): pd.Timestamp("1999-02-05"),
    ("las_palmas", "co_horario"): pd.Timestamp("2000-12-01"),
    ("las_palmas", "mp10_horario"): pd.Timestamp("2007-08-02"),
    ("las_palmas", "direccion_viento_horario"): pd.Timestamp("2007-10-01"),
    ("las_palmas", "mp25_horario"): pd.Timestamp("2020-04-22"),
    ("los_maitenes", "so2_horario"): pd.Timestamp("1993-03-31"),
    ("los_maitenes", "so2_diario"): pd.Timestamp("2000-08-21"),
    ("los_maitenes", "mp10_diario"): pd.Timestamp("2000-08-22"),
    ("los_maitenes", "o3_horario"): pd.Timestamp("2009-09-01"),
    ("los_maitenes", "mp25_diario"): pd.Timestamp("2012-07-29"),
    ("puchuncavi", "so2_horario"): pd.Timestamp("1993-01-01"),
    ("puchuncavi", "no2_horario"): pd.Timestamp("2009-08-31"),  # excepción, ver arriba
    ("puchuncavi", "o3_horario"): pd.Timestamp("2010-01-30"),
    ("puchuncavi", "direccion_viento_horario"): pd.Timestamp("2009-12-31"),
    ("puchuncavi", "velocidad_viento_horario"): pd.Timestamp("2009-12-31"),
    ("puchuncavi", "mp10_horario"): pd.Timestamp("2016-02-01"),
    ("puchuncavi", "mp25_horario"): pd.Timestamp("2016-02-01"),
    ("ventanas", "so2_horario"): pd.Timestamp("2013-01-01"),
    ("ventanas", "no2_horario"): pd.Timestamp("2013-01-01"),
    ("ventanas", "o3_horario"): pd.Timestamp("2013-01-01"),
    ("ventanas", "mp10_horario"): pd.Timestamp("2013-01-01"),
    ("ventanas", "mp25_horario"): pd.Timestamp("2013-01-01"),
    ("ventanas", "direccion_viento_horario"): pd.Timestamp("2013-01-01"),
    ("ventanas", "velocidad_viento_horario"): pd.Timestamp("2013-01-01"),
}

# Ventanas de falla de sensor DENTRO del periodo de operación (CLAUDE.md
# §8.6.5): a diferencia de INICIO_OPERACION, esto no es "la estación no
# existía todavía" sino "el instrumento se cayó un rato mientras ya
# funcionaba". Medido el 2026-09-17 sobre los 8 pares (estación, parámetro)
# de viento, buscando tramos con al menos una lectura fuera de rango físico
# y extendidos hacia ambos lados mientras la cobertura horaria en una
# vecindad de 6 horas se mantuviera por debajo del 50 % -- es la única
# ventana que existe: los otros 7 pares no tienen ni una sola lectura fuera
# de rango en todo su periodo de operación.
#
# la_greda, 2021-01-15 07:00 a 2021-01-17 16:00 (58 horas). SO2 de la_greda
# funciona con normalidad las 72 horas de ese rango (0 huecos, 3,3-28,1
# µg/m³): la falla es solo meteorológica, no afecta al contaminante que
# importa a este repositorio.
#   - direccion_viento_horario: 53 de 58 horas nulas; 4 fuera de rango
#     (-1,09e8; -1,10e-29; -2,26e-17; 1,29e11 grados); 1 hora "en rango"
#     que en realidad es ruido de piso del instrumento (2,03e-20 grados),
#     no una lectura real.
#   - velocidad_viento_horario: el algoritmo por sí solo encuentra un tramo
#     más corto (46-53 horas, 09:00 del 15 a 13:00 del 17) porque cuatro de
#     sus horas "en rango" son ruido de piso casi cero (9,2e-33; 2,0e-20
#     dos veces; 2,7e-14 m/s -- el "cero" que un sensor caído informa, no
#     una calma real) que interrumpen la racha de nulos; se declara la
#     misma ventana que dirección porque es el mismo instrumento fallando y
#     las horas de diferencia (07:00-09:00, 13:00-16:00) también son nulas
#     en velocidad, no datos reales excluidos de más.
# Ningún cero de viento fuera de esta ventana se toca: la calma real existe
# y es un dato legítimo (CLAUDE.md §8.6.5) -- lo que se declara es la
# ventana, nunca el valor.
VENTANAS_FALLA_SENSOR: list[tuple[str, str, pd.Timestamp, pd.Timestamp]] = [
    (
        "la_greda",
        "direccion_viento_horario",
        pd.Timestamp("2021-01-15 07:00:00"),
        pd.Timestamp("2021-01-17 16:00:00"),
    ),
    (
        "la_greda",
        "velocidad_viento_horario",
        pd.Timestamp("2021-01-15 07:00:00"),
        pd.Timestamp("2021-01-17 16:00:00"),
    ),
]


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


def claves_desconocidas(df: pd.DataFrame) -> set[tuple[str, str]]:
    """Pares (estación, parámetro) de `df` que no están en `INICIO_OPERACION`."""
    claves = set(zip(df["estacion"], df["parametro"], strict=True))
    return claves - INICIO_OPERACION.keys()


def validar_claves_conocidas(df: pd.DataFrame) -> None:
    """Falla ruidosamente si `df` trae un par (estación, parámetro) que
    `INICIO_OPERACION` no mide (CLAUDE.md §8.6.4, paso 2).

    Deliberadamente NO se detecta el inicio de operación en tiempo de
    ejecución: un umbral que se recalcula solo puede desplazarse en silencio
    cuando cambien los datos -- hay que medirlo primero. Se llama desde
    `data.load_validated` ANTES de invocar pandera, y no desde dentro de un
    `pa.Check`: pandera, en modo `lazy`, atrapa cualquier excepción que lance
    un check y la convierte en un "CHECK_ERROR" sin fila asociada -- la
    excepción nunca llegaría a quien llama, y la fila pasaría como válida sin
    ningún aviso. Ver tests/test_schema.py::TestInicioOperacion.
    """
    desconocidas = claves_desconocidas(df)
    if desconocidas:
        raise ValueError(
            "INICIO_OPERACION no tiene entrada para "
            f"{sorted(desconocidas)}. Mide su cobertura por año y revisa si "
            "sus valores tempranos son física o físicamente plausibles antes "
            "de añadirlo (CLAUDE.md §8.6.4) -- no asumas un valor."
        )


def fecha_posterior_a_inicio_operacion(df: pd.DataFrame) -> pd.Series:
    """True donde `fecha_hora` es posterior al inicio de operación medido de
    esa (estación, parámetro).

    Asume que `validar_claves_conocidas` ya corrió (así lo hace
    `data.load_validated`); un par sin entrada compara contra `NaT` y por
    tanto falla el check, en vez de lanzar dentro de pandera.
    """
    inicio = pd.Series(
        [
            INICIO_OPERACION.get(clave, pd.NaT)
            for clave in zip(df["estacion"], df["parametro"], strict=True)
        ],
        index=df.index,
    )
    return df["fecha_hora"] >= inicio


def fecha_no_es_futura(df: pd.DataFrame) -> pd.Series:
    """True donde `fecha_hora` no es posterior a hoy."""
    hoy = pd.Timestamp(dt.date.today()) + pd.Timedelta(days=1)
    return df["fecha_hora"] <= hoy


def _dentro_de_ventana_falla_sensor(df: pd.DataFrame) -> pd.Series:
    dentro = pd.Series(False, index=df.index)
    for estacion, parametro, inicio, fin in VENTANAS_FALLA_SENSOR:
        dentro |= (
            (df["estacion"] == estacion)
            & (df["parametro"] == parametro)
            & (df["fecha_hora"] >= inicio)
            & (df["fecha_hora"] <= fin)
        )
    return dentro


def fuera_de_ventana_falla_sensor(df: pd.DataFrame) -> pd.Series:
    """True donde la fila NO es un valor no nulo dentro de una ventana de
    falla de sensor declarada (CLAUDE.md §8.6.5).

    Una fila nula dentro de la ventana pasa (es exactamente el hueco que la
    ventana declara); una fila con valor dentro de la ventana no pasa --
    incluido un valor que por sí solo respetaría el rango físico, como los
    ceros de ruido de piso descritos junto a `VENTANAS_FALLA_SENSOR`. No se
    imputa nada: la fila va a cuarentena y el hueco queda explícito.
    """
    dentro = _dentro_de_ventana_falla_sensor(df)
    return ~(dentro & df["valor"].notna())


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
        pa.Check(fecha_posterior_a_inicio_operacion, error="fecha_anterior_a_operacion"),
        pa.Check(fecha_no_es_futura, error="fecha_futura"),
        pa.Check(fuera_de_ventana_falla_sensor, error="ventana_de_falla_de_sensor"),
    ],
    strict=False,
    coerce=False,
)
