# CLAUDE.md — Contexto permanente del proyecto

> Se carga automáticamente en cada sesión de Claude Code. **Es la fuente de
> verdad. Si un prompt contradice esto, gana esto.**
> Todo número marcado como verificado se midió ejecutando código sobre los CSV
> reales. Si tu código produce otro valor, **para y repórtalo**: no ajustes el
> valor esperado para que el test pase.

---

## 1. Identidad del proyecto

Portafolio público de **@ajmedinaa-gif**. Segundo repositorio, después de
`predictive-maintenance-pipeline`.

**Tesis:** *el 31 de mayo de 2023 cerró la Fundición Ventanas tras 58 años.
Tres estaciones de monitoreo independientes llevaban 33 años midiendo SO₂ cada
hora a su alrededor. Este repositorio mide qué cambió — y demuestra, por el
camino, que el dato público con el que cualquier ciudadano consulta la calidad
del aire de su comuna nunca habría mostrado los episodios que sí ocurrieron.*

Tres ejes, en este orden:

1. **La recuperación medida.** De 1.851 horas en nivel de emergencia entre 1993
   y 1999 a **cero desde 2020**, en tres estaciones a la vez. Series temporales
   interrumpidas alrededor de un evento con fecha exacta.
2. **Los límites del dato público.** Cero superaciones de norma en resolución
   diaria frente a 1.323 horas de emergencia en la misma serie, misma estación,
   mismo periodo.
3. **Pronóstico horario.** Regresión del SO₂ a una hora vista con meteorología,
   con validación estrictamente temporal.

El repo no vende un modelo. Vende evidencia sobre un lugar real.

## 2. Reglas duras — nunca violar

1. **Validación TEMPORAL, nunca aleatoria.** Los datos son una serie de tiempo:
   `TimeSeriesSplit` o cortes por año. Un `train_test_split` aleatorio sobre
   estos datos es fuga de información y anula todo el repositorio.
2. **Ningún número del README, informes o notebooks se escribe a mano.** Todo
   sale de `reports/*.json` generado por el pipeline. Hay un test que lo
   verifica.
3. **Los CSV crudos de SINCA NO se versionan** (112 MB). El pipeline los ingiere
   a un Parquet consolidado que sí va al repo. Ver §11.
4. **Los datos que no pasan el contrato van a `data/quarantine/`.** No se borran
   ni se imputan en silencio.
5. **Toda afirmación sobre el efecto del cierre va acompañada de sus
   confusores.** No tenemos grupo de control limpio ni meteorología completa
   para todo el periodo: el análisis es observacional y se declara como tal.
6. **Semillas fijadas.** Dos ejecuciones consecutivas producen resultados
   idénticos. Semilla 42, definida una sola vez en `config/default.yaml`.
7. **Sin llamadas de red en tiempo de ejecución del pipeline.**
8. **Un commit por unidad conceptual.** Jamás `git push --force` sobre `main`.
9. **Al final de cada fase: parar y presentar el CHECKPOINT.** No continuar sin
   aprobación explícita de la usuaria.
10. Español en documentación y comentarios; inglés en nombres de código y en los
    mensajes de commit.
11. **Las figuras PNG de `reports/figures/` y los JSON de `reports/` SÍ se
    versionan**, a propósito: el destinatario del repo no ejecuta el código, y
    el dashboard desplegado los necesita para arrancar.

## 3. Formato del CHECKPOINT

```
## CHECKPOINT Fase N — <nombre>

### Qué se construyó
### Ficheros creados/modificados (con nº de líneas)
### Comandos ejecutados y su salida real   (pegar, no parafrasear)
### Números medidos en esta fase  (marcar los que NO coinciden con CLAUDE.md)
### Tests: X pasan / Y fallan / Z omitidos — cobertura N%
### Commit  (hash corto + mensaje)
### Decisiones que tomé y que podrías querer revertir
### Bloqueos o supuestos
### Qué deberías verificar tú antes de seguir
```

## 4. Convención de commits

Conventional Commits en inglés:

```
feat(ingest): parse SINCA hourly exports into a tidy parquet
fix(schema): quarantine the 90114 m/s wind speed reading
test(recovery): assert the 2023 breakpoint is detected at all three stations
docs(readme): add the daily-vs-hourly resolution finding
```

## 5. Stack

`uv` · `pandas` · `numpy` · `pyarrow` · `scipy` · `statsmodels` · `ruptures`
(detección de puntos de quiebre) · `scikit-learn` · `pandera` ·
`pydantic-settings` · `typer` · `jinja2` · `matplotlib` · `streamlit` ·
`pytest` + `pytest-cov` + `hypothesis` · `ruff` · `pre-commit` · Docker ·
GitHub Actions.

**Fuera:** `mypy --strict`, `mlflow`, Homebrew (ver §14).
Cobertura objetivo: **80 %**.

## 6. El contexto: qué es este lugar

Quintero-Puchuncaví, región de Valparaíso, es una de las zonas de sacrificio
ambiental más documentadas de Chile. El complejo industrial de Ventanas incluyó
durante 58 años la fundición de cobre de Codelco.

**El evento central: el 31 de mayo de 2023 comenzó la primera fase del cierre de
la Fundición Ventanas** (apagado de hornos y calderas). Es un evento con fecha
exacta, público y verificable — el ancla del análisis de series interrumpidas.

Hitos previos relevantes para interpretar la serie: el episodio de intoxicación
de escolares en La Greda (2011) y la crisis de intoxicaciones masivas de
Quintero (agosto de 2018).

## 7. La norma: D.S. 104/2018

Norma primaria de calidad del aire para SO₂:

| ventana | valor |
|---|---|
| 1 hora | **350 µg/m³N** |
| 24 horas | 150 µg/m³N |
| Anual | 60 µg/m³N |
| **Emergencia ambiental** (ICAG SO₂ ≥ 200) | **≥ 500 µg/m³N en 1 hora** |

En este repositorio, **"episodio" = una hora con SO₂ ≥ 500 µg/m³N**, es decir el
umbral legal de emergencia ambiental. Es un umbral fijado por decreto, no un
percentil elegido por conveniencia.

## 8. Datos verificados

Formato SINCA: separador `;`, decimal con coma, fecha `YYMMDD` (YY < 50 → 20YY),
hora `HHMM`. Tres columnas de estado: `Registros validados`,
`Registros preliminares`, `Registros no validados` — el valor aparece en **una**
de las tres.

### 8.1 Inventario (todo horario salvo donde diga diario)

| estación | parámetro | periodo | filas | cobertura |
|---|---|---|---|---|
| los_maitenes | SO₂ | 1993-03-31 → 2026-09-14 | 293.303 | 97 % |
| la_greda | SO₂ | 1993-01-01 → 2026-09-15 | 295.463 | 99 % |
| puchuncavi | SO₂ | 1993-01-01 → 2026-09-15 | 295.463 | 99 % |
| ventanas | SO₂ | 2013-01-01 → 2026-09-14 | 120.119 | 98 % |
| las_palmas | SO₂ | 1999-02-06 → 2026-09-14 | 241.991 | 91 % |
| puchuncavi | dir. y vel. viento | 2009-12-31 → 2026-09-16 | 146.495 | 99 % |
| ventanas | dir. y vel. viento | 2013-01-01 → 2026-09-15 | 120.143 | 98 % |
| la_greda | dir. y vel. viento | 1970-01-01 → 2026-09-16 | 497.111 | **29 %** |
| las_palmas | dir. viento | 2007-10-01 → 2026-07-10 | 164.591 | 42 % |
| los_maitenes | SO₂ **diario** | 2000-08-21 → 2026-08-20 | 9.496 | 99,3 % |

`las_palmas` es la estación de contraste urbano (Viña del Mar), fuera de la
influencia del complejo industrial.

### 8.2 Episodios de SO₂ — el núcleo del repositorio

| estación | horas válidas | ≥ 350 (norma) | ≥ 500 (emergencia) |
|---|---|---|---|
| los_maitenes | 287.088 | 2.494 | **1.323** |
| la_greda | 292.514 | 772 | 354 |
| puchuncavi | 293.070 | 962 | 311 |
| **total** | **872.672** | **4.228** | **1.988** |

**Emergencias por periodo, las tres estaciones sumadas:**

| periodo | horas en emergencia |
|---|---|
| 1993–1999 | **1.851** |
| 2000–2009 | 132 |
| 2010–2019 | 5 |
| **2020–2026** | **0** |

**Máximos anuales (µg/m³), los tres a la vez:**

| año | los_maitenes | la_greda | puchuncavi |
|---|---|---|---|
| 1995 | 997 | 998 | 966 |
| 2018 | 480 | 307 | 143 |
| 2023 | 357 | 90 | 37 |
| **2024** | **29** | **16** | **24** |
| 2025 | 39 | 14 | 40 |
| 2026 | 36 | 18 | 36 |

El cierre empezó el **31 de mayo de 2023**; 2024 es el primer año completo sin
fundición. El desplome simultáneo en tres instrumentos independientes es la
observación central.

### 8.3 El hallazgo de resolución

En `los_maitenes`, mismo contaminante, mismo periodo:

| | superaciones |
|---|---|
| Serie **diaria** (2000–2026), norma 24 h de 150 µg/m³ | **2 en 26 años, ninguna desde 2019** |
| Serie diaria, máximo histórico | 157,58 µg/m³ |
| Serie **horaria**, emergencias ≥ 500 | **1.323** |

**Verificado:** promediar la serie horaria a diaria reproduce la serie diaria
publicada en **99,9 % de 9.427 días**, con diferencia mediana **0,000 µg/m³**.
No son datos distintos: es el mismo dato a otra resolución.

Corolario que el repositorio debe enunciar sin adornos: un promedio de 24 horas
diluye un pico de dos horas hasta hacerlo invisible, y la resolución diaria es
la que se ofrece por defecto al público.

### 8.4 En 2018 el SO₂ no fue el agente

El año de las intoxicaciones masivas de Quintero, `los_maitenes` registró un
máximo de **480 µg/m³** y **cero horas** en nivel de emergencia. Reportarlo como
hallazgo, sin especular sobre cuál fue el agente: los datos de hidrocarburos
disponibles son diarios y su máximo es 0–1 ppm, insuficiente para concluir nada.

### 8.5 Material particulado: no hay evento raro

`los_maitenes`, serie diaria completa: **2 días** sobre la norma de MP2,5
(50 µg/m³ 24 h) y **4 días** sobre la de MP10 (150 µg/m³ 24 h). No hay problema
de clasificación de eventos raros en este contaminante. No lo fuerces.

### 8.6 Anomalías conocidas — material para el contrato de datos

1. **Cero registros "validados".** En los 11 contaminantes de la serie diaria de
   `los_maitenes`, ni una sola medición está marcada como validada: todo es
   preliminar o no validado. Para SO₂: 5.614 preliminares, 3.813 no validados,
   69 vacíos. **Verificar si es un artefacto de la opción de descarga antes de
   afirmarlo en el README.**
2. **`la_greda`, velocidad de viento: máximo 90.114,5 m/s.** Imposible físico —
   el récord mundial ronda los 113 m/s. Es el caso de cuarentena del proyecto,
   equivalente a la vibración negativa del repositorio anterior.
3. **Cobertura meteorológica muy desigual**: 99 % en `puchuncavi` desde 2009,
   29 % en `la_greda` pese a arrancar en 1970.
4. La descarga original traía ficheros sin identificar el parámetro en el
   nombre, duplicados exactos, y ficheros que eran tablas resumen (rosas de
   vientos) en vez de series. Ya resuelto en `data/raw/`, pero **documentarlo**:
   es el problema real de ingesta desde una fuente pública.

## 9. Protocolo de análisis

### 9.1 Recuperación y efecto del cierre

- Serie mensual y anual de: horas en emergencia, máximo, percentil 99, media.
- Detección de puntos de quiebre sin supervisión (`ruptures`, PELT) sobre la
  serie completa, **sin decirle dónde está 2023**: si el método encuentra el
  quiebre solo, el argumento es mucho más fuerte.
- Serie temporal interrumpida alrededor del 2023-05-31, con `las_palmas` como
  contraste urbano.
- **Confusores obligatorios en el texto:** no hay grupo de control no expuesto
  dentro de la bahía; la meteorología no cubre todo el periodo; hubo otros
  cambios regulatorios y operativos en 33 años; y la pandemia de 2020 coincide
  con parte del descenso. El análisis es observacional.

### 9.2 Pronóstico horario

- Objetivo: SO₂ de la hora siguiente en `los_maitenes` (regresión).
- Predictores: rezagos de SO₂, dirección y velocidad de viento (`puchuncavi`
  desde 2009 es la serie meteorológica con mejor cobertura), hora del día, mes.
- **Dirección del viento es circular**: NUNCA usarla como número en grados.
  Descomponer en `sin(θ)` y `cos(θ)`. Un modelo que trate 359° y 1° como
  extremos opuestos está roto.
- Validación: `TimeSeriesSplit` o cortes por año. Entrenar en años anteriores,
  evaluar en posteriores. Jamás aleatoria.
- Línea base obligatoria: **persistencia** (el valor de la hora anterior).
  Cualquier modelo que no la supere no aporta nada, y en series horarias de
  contaminación la persistencia es sorprendentemente difícil de batir.

## 10. Los cuatro extras que diferencian este repo

1. **Detección de quiebre a ciegas** que reencuentra el cierre de 2023 sin que
   se le diga la fecha.
2. **La demostración diario-vs-horario**, verificada por reconstrucción.
3. **Cuarentena de imposibles físicos** (los 90.114 m/s).
4. **Dashboard** con selector de estación, línea de tiempo de episodios y los
   hitos (2011, 2018, cierre 2023) marcados.

## 11. Datos: qué se versiona y qué no

- `data/raw/` — 112 MB de CSV de SINCA. **NO se versiona.** Va en `.gitignore`.
- `data/processed/sinca.parquet` — tabla larga consolidada
  (`estacion`, `parametro`, `fecha_hora`, `valor`, `estado`). **SÍ se versiona**
  si pesa menos de 25 MB; medirlo en la Fase 1 y reportarlo. Si se pasa,
  versionar solo SO₂ y viento, y documentar la decisión.
- El README documenta cómo rehacer la descarga desde
  `https://sinca.mma.gob.cl/` con las estaciones y parámetros exactos.

## 12. Estructura del repositorio

```
src/calidad_aire/   ingest, schema, data, eda, figures, recovery, forecast,
                    report, cli
tests/              cobertura >= 80 %
config/             default.yaml
data/raw/           CSV de SINCA (NO versionado)
data/processed/     sinca.parquet (versionado)
data/quarantine/
notebooks/
app/streamlit_app.py
reports/            json, md, figures/, html
tools/fase.py
.github/workflows/
```

## 13. Fuentes a citar en el README

- **SINCA** — Sistema de Información Nacional de Calidad del Aire, Ministerio
  del Medio Ambiente. `https://sinca.mma.gob.cl/`
- **D.S. 104/2018**, norma primaria de calidad del aire para SO₂, MMA.
- **Cierre de la Fundición Ventanas (Codelco)**, primera fase el 31 de mayo de
  2023, tras 58 años de operación.
- Killick, Fearnhead & Eckley (2012), *Optimal detection of changepoints with a
  linear computational cost* — método PELT.
- Bernal, Cummins & Gasparrini (2017), *Interrupted time series regression for
  the evaluation of public health interventions* — protocolo de series
  interrumpidas.

## 14. Entorno de desarrollo: macOS Intel

Entorno verificado: MacBook Air **Intel (x86_64)**, zsh, `uv` en `~/.local/bin`,
Python del sistema 3.9.6 (no usar), `gh` autenticado como `ajmedinaa-gif`,
**sin Docker instalado**, sin conda en el PATH.

### 14.1 Nunca `python`, `pip` ni `pytest` a secas

El Python del sistema es 3.9.6 y el proyecto necesita 3.11. Siempre `uv run …`.
En el `Makefile`, **todos** los targets llaman a `uv run`.

### 14.2 Homebrew no sirve en esta máquina

Desde septiembre de 2026 Homebrew dejó de publicar binarios precompilados para
macOS Intel x86_64: cada `brew install` compila desde fuente. **Nunca propongas
`brew install`.** Alternativas: un paquete de PyPI vía `uv add`, o un binario
oficial precompilado. Las dependencias Python no se ven afectadas: todas tienen
rueda `macosx_x86_64`.

### 14.3 Pegar comandos de uno en uno

Varios comandos abren prompts interactivos. Si se pega un bloque de varias
líneas, el shell entrega las siguientes como respuesta al prompt y se pierden.

### 14.4 matplotlib sin interfaz gráfica

`matplotlib.use("Agg")` **antes** de importar pyplot. Guardar con `fig.savefig` +
`plt.close(fig)`. Nunca `plt.show()`.

### 14.5 Utilidades BSD, no GNU

`sed -i` requiere argumento en macOS; mejor no usarlo. `date`, `stat`, `find`
tienen banderas distintas. `make` es GNU Make 3.81: sin `.ONESHELL`.
**Regla: todo lo que el pipeline necesite hacer, lo hace Python.**

### 14.6 `.gitignore`

Obligatorio: `.DS_Store`, `._*`, `.Spotlight-V100`, `.Trashes`, `__MACOSX`,
`.venv/`, **`data/raw/`**, `data/quarantine/*`, `reports/*.html`.

### 14.7 Docker: lo construye CI, no esta máquina

x86_64 coincide con `ubuntu-latest`: **no** añadas `--platform`. El `Dockerfile`
se escribe y se versiona, pero **el job `docker` de CI es lo que prueba que
funciona**, y no puede ser opcional ni `continue-on-error`. No pidas a la
usuaria ejecutar `docker build`.

**Trampa conocida del repositorio anterior:** `uv sync` instala el proyecto en
modo **editable** por defecto, y en un Dockerfile multi-stage eso deja el venv
apuntando a una ruta que no existe en el stage final. Usa
`uv sync --frozen --no-dev --no-editable`.

### 14.8 Sistema de ficheros insensible a mayúsculas

APFS no distingue `Data/` de `data/`; Linux y GitHub sí. Nombres en minúsculas.

### 14.9 `.pth` ocultos rompen el install editable

**Trampa verificada en esta máquina (Fase 1, 2026-09-16):** tras el primer
`uv sync`, los ficheros `.pth` de `.venv/lib/python3.11/site-packages/`
(incluido el del install editable del propio proyecto) quedaron con el flag
BSD `hidden` puesto (visible con `ls -lO`). Python 3.11.16 salta los `.pth`
ocultos al arrancar (`site.addpackage`), así que `import calidad_aire` y
`caq` fallaban con `ModuleNotFoundError` incluso pasando por `uv run`,
mientras que `uv run python -c "import sys; print(sys.executable)"` seguía
apuntando bien al `.venv`. Se reprodujo determinísticamente y se confirmó con
`ls -lO` + `python -v -c pass` (site.py imprime "Skipping hidden .pth file").
`make install` ahora corre `chflags -R nohidden` sobre esos ficheros después
de `uv sync`. Si vuelve a pasar (p.ej. tras un `.venv` nuevo), el síntoma es
el mismo: `caq` o `import calidad_aire` fallan pero el intérprete es el
correcto. No es un bug del código del proyecto.
