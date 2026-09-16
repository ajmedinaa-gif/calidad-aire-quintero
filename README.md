# calidad-aire-quintero

SO₂ en Quintero-Puchuncaví: 33 años de datos horarios en tres estaciones, y
qué cambió tras el cierre de la Fundición Ventanas.

> **Estado del repositorio: Fase 1 de 5 — ingesta y contrato de datos.**
> Todavía no hay análisis, figuras ni modelos. Lo que sigue en este README es
> exclusivamente lo que produce el pipeline de esta fase: inventario de datos
> y contrato de calidad. El resto llega en las fases siguientes.

## El problema

El 31 de mayo de 2023 comenzó el cierre de la Fundición Ventanas de Codelco,
tras 58 años de operación en la bahía de Quintero-Puchuncaví, una de las
zonas de sacrificio ambiental más documentadas de Chile. Tres estaciones de
monitoreo de SINCA (Sistema de Información Nacional de Calidad del Aire),
independientes entre sí, llevan alrededor de 33 años midiendo SO₂ cada hora
alrededor del complejo industrial.

Este repositorio hace dos cosas con esos datos:

1. Mide qué cambió antes y después del cierre, con la evidencia de tres
   instrumentos a la vez (fases 2 y 3).
2. Muestra, con reconstrucción numérica, que el dato público que cualquier
   persona consulta en resolución diaria nunca habría mostrado los episodios
   de emergencia ambiental que sí ocurrieron por SO₂ (fase 2).

No es un ejercicio de modelamiento: es evidencia sobre un lugar real, con sus
confusores declarados explícitamente.

## Los datos

Fuente: [SINCA](https://sinca.mma.gob.cl/), Ministerio del Medio Ambiente de
Chile. Descarga horaria (y diaria donde se indica) para cinco estaciones de
la bahía. `las_palmas` (Viña del Mar) es la estación de contraste urbano,
fuera de la influencia directa del complejo industrial.

| estación | parámetro | periodo | filas | cobertura |
|---|---|---|---|---|
| los_maitenes | SO₂ | 1993-03-31 → 2026-09-14 | 293.303 | 97 % |
| la_greda | SO₂ | 1993-01-01 → 2026-09-15 | 295.463 | 99 % |
| puchuncavi | SO₂ | 1993-01-01 → 2026-09-15 | 295.463 | 99 % |
| ventanas | SO₂ | 2013-01-01 → 2026-09-14 | 120.119 | 98 % |
| las_palmas | SO₂ | 1999-02-06 → 2026-09-14 | 241.991 | 91 % |
| puchuncavi | dirección y velocidad de viento | 2009-12-31 → 2026-09-16 | 146.495 | 99 % |
| ventanas | dirección y velocidad de viento | 2013-01-01 → 2026-09-15 | 120.143 | 98 % |
| la_greda | dirección y velocidad de viento | 1970-01-01 → 2026-09-16 | 497.111 | 29 % |
| las_palmas | dirección de viento | 2007-10-01 → 2026-07-10 | 164.591 | 42 % |
| los_maitenes | SO₂ diario | 2000-08-21 → 2026-08-20 | 9.496 | 99,3 % |

`filas` es el número de registros del CSV crudo (con o sin valor); la
cobertura real de cada serie se calcula en la fase 2.

### El contrato de datos

Cada CSV crudo se convierte a una fila `(estacion, parametro, fecha_hora,
valor, estado)`. `parametro` conserva la resolución temporal en el nombre del
fichero (p.ej. `so2_horario` frente a `so2_diario`): son series distintas y
no se mezclan bajo la misma clave.

Rangos físicos exigidos antes de que un valor se considere válido:

| parámetro | rango |
|---|---|
| SO₂, NO₂, O₃, MP10, MP25, CO | ≥ 0 |
| dirección de viento | 0° – 360° |
| velocidad de viento | 0 – 60 m/s |
| fecha_hora | 1970-01-01 – hoy |

Lo que no cumple el contrato **no se borra ni se imputa**: va a
`data/quarantine/<timestamp>.csv` con una columna `motivo`. El caso conocido
de esta descarga es una lectura de **90.114,5 m/s** de velocidad de viento en
`la_greda` — muy por encima del récord mundial (≈113 m/s).

### Qué se versiona y qué no

- `data/raw/` (112 MB de CSV de SINCA) **no se versiona**: está en
  `.gitignore`. Ver más abajo cómo rehacer la descarga.
- `data/processed/sinca.parquet` sí se versiona, pero **solo con SO₂ y
  viento** (dirección y velocidad), con `estacion`/`parametro`/`estado` como
  `category`, `valor` en `float32` y compresión `zstd` (nivel 15): con los 11
  parámetros completos pesa 56 MB (34 MB incluso con esas mismas
  optimizaciones y zstd nivel 19), por encima del límite de 25 MB fijado para
  este repositorio; con SO₂ y viento pesa **19,62 MB**. NO₂, O₃, MP10, MP25 y
  CO quedan validados durante la ingesta pero no persistidos — se recuperan
  re-ejecutando `caq ingest` sobre `data/raw/`. SO₂ y viento son, además, los
  únicos
  parámetros que usan las fases 2 a 4 (recuperación y pronóstico).
- `data/quarantine/` tampoco se versiona (son datos derivados,
  reproducibles desde `data/raw/`).

### Cómo rehacer la descarga

1. Ir a <https://sinca.mma.gob.cl/> → Consulta de datos.
2. Para cada estación (`Los Maitenes`, `La Greda`, `Puchuncaví`, `Ventanas`,
   `Las Palmas`) y cada parámetro (`SO2`, `NO2`, `O3`, `MP10`, `MP2,5`, `CO`
   donde exista, dirección y velocidad de viento), exportar la serie
   **por registro** (no una tabla resumen / rosa de vientos) en resolución
   horaria — y, para `los_maitenes`, también la diaria de SO₂, MP10 y MP2,5.
3. Guardar cada export como
   `data/raw/<estacion>/<parametro>_<resolucion>.csv`, por ejemplo
   `data/raw/los_maitenes/so2_horario.csv`. El nombre del fichero es la
   fuente de verdad del parámetro para el pipeline.
4. Ejecutar `make ingest` (equivalente a `uv run caq ingest`).

## Quickstart

```bash
uv sync
make lint
make test
make ingest
```

Todos los comandos pasan por `uv run`: el Python del sistema en macOS es
3.9.6 y el proyecto necesita 3.11.

## Estructura

```
src/calidad_aire/   ingest, schema, data, cli
tests/              cobertura >= 80 %
config/             default.yaml (semilla 42)
data/raw/           CSV de SINCA (no versionado)
data/processed/     sinca.parquet (versionado, solo SO2 y viento)
data/quarantine/    filas que violan el contrato (no versionado)
tools/fase.py
```

## Fuentes

- **SINCA** — Sistema de Información Nacional de Calidad del Aire, Ministerio
  del Medio Ambiente. <https://sinca.mma.gob.cl/>
- **D.S. 104/2018**, norma primaria de calidad del aire para SO₂, MMA.
- **Cierre de la Fundición Ventanas (Codelco)**, primera fase el 31 de mayo de
  2023, tras 58 años de operación.

## Autor

[@ajmedinaa-gif](https://github.com/ajmedinaa-gif)
