# Plan de construcción — 5 fases

Pega **un prompt por vez** en Claude Code. Cuando presente el CHECKPOINT,
ejecuta tú los comandos que dice haber ejecutado, y solo entonces pega el
siguiente.

## Antes de empezar

```bash
cd ~/proyectos/calidad-aire-quintero
python3 tools/fase.py 1 | pbcopy
claude
```

`/clear` entre fases. `Esc` para interrumpir. Los datos ya están en
`data/raw/`, renombrados y organizados por estación.

---

# FASE 1 — Andamiaje, ingesta de SINCA y contrato de datos

```
Lee CLAUDE.md completo antes de hacer nada. Esta es la Fase 1.

OBJETIVO: convertir 112 MB de CSV de SINCA, en cinco estaciones, en un único
parquet consolidado y validado, con las lecturas imposibles en cuarentena.

A. Andamiaje
1. git init y la estructura de CLAUDE.md §12.
2. pyproject.toml con uv: nombre calidad-aire-quintero, requires-python
   ">=3.11", dependencias de §5, script de consola
   caq = "calidad_aire.cli:app". Ruff line-length 100, reglas
   E,F,I,N,UP,B,SIM,RUF. pytest --cov=src --cov-fail-under=80. SIN mypy.
3. uv python pin 3.11, uv sync, y muestra la salida de
   `uv run python -c "import sys; print(sys.executable)"`: debe apuntar al
   .venv del proyecto.
4. .pre-commit-config.yaml con ruff-format, ruff y check-added-large-files.
5. .gitignore según CLAUDE.md §14.6. data/raw/ NO se versiona.
6. LICENSE MIT a nombre de ajmedinaa-gif.
7. cli.py con typer y un comando `version` + tests/test_cli.py.
8. Makefile: install, lint, test, ingest, all. Todo vía `uv run`.

B. Ingesta — el corazón de esta fase
9. src/calidad_aire/ingest.py:
   - parse_fecha_hora(fecha, hora): YYMMDD con YY<50 -> 20YY, HHMM. Devuelve
     datetime. Hay datos desde 1970 y hasta 2026: la regla del siglo importa.
   - leer_sinca(path) -> DataFrame con columnas fecha_hora, valor, estado,
     donde estado ∈ {validado, preliminar, no_validado, ausente} según cuál de
     las tres columnas de SINCA trae el valor (CLAUDE.md §8).
   - Decimal con coma, separador ;, encoding latin-1.
   - Algunos ficheros de SINCA son TABLAS RESUMEN (rosas de vientos), no series:
     detéctalo y falla con un mensaje claro, no con un stack trace.
10. consolidar() -> tabla larga (estacion, parametro, fecha_hora, valor, estado)
    recorriendo data/raw/<estacion>/<parametro>.csv. El nombre del fichero es
    la fuente de verdad del parámetro.
11. Escribe data/processed/sinca.parquet. MIDE su tamaño y repórtalo en el
    CHECKPOINT: si supera 25 MB, versiona solo SO₂ y viento y documenta la
    decisión (CLAUDE.md §11).

C. Contrato
12. schema.py con pandera: rangos físicos por parámetro.
    - so2, no2, o3, mp10, mp25: >= 0
    - direccion_viento: 0 a 360
    - velocidad_viento: 0 a 60 m/s  (el récord mundial ronda 113 m/s; 60 es
      generoso y deja fuera el imposible conocido)
    - fecha_hora entre 1970-01-01 y hoy
13. data.py con load_validated(): las filas que violan el contrato van a
    data/quarantine/<timestamp>.csv con columna motivo.
14. CLI `caq ingest` que ejecuta todo e imprime el informe.

D. Verificación
15. tests/test_ingest.py que comprueba contra CLAUDE.md §8.1 y §8.2, tolerancia
    1e-3. Si un valor no coincide, PARA y repórtalo. En particular:
    - los_maitenes/so2_horario: 287.088 horas con valor, 1.323 >= 500,
      2.494 >= 350
    - la_greda: 292.514 válidas, 354 >= 500
    - puchuncavi: 293.070 válidas, 311 >= 500
    - emergencias por periodo: 1993-1999 = 1.851, 2020-2026 = 0
16. tests/test_schema.py: la lectura de 90.114,5 m/s de la_greda termina en
    cuarentena con el motivo correcto. Cuenta cuántas filas quedan en cuarentena
    EN TOTAL y repórtalo: quiero saber si es una o son muchas.
17. Test de la regla del siglo: parse_fecha_hora("700101","0100") da 1970 y
    ("260101","0100") da 2026.
18. make lint && make test en verde.
19. README mínimo: título, el problema, la tabla de inventario de §8.1 con
    números reales, y cómo rehacer la descarga desde sinca.mma.gob.cl.
    NO inventes resultados: en esta fase no hay análisis todavía.
20. Commits con Conventional Commits. Crea el repo y haz push:
    gh repo create ajmedinaa-gif/calidad-aire-quintero --public \
      --description "SO2 en Quintero-Puchuncaví: 33 años de datos horarios en tres estaciones, y qué cambió tras el cierre de la Fundición Ventanas" \
      --source=. --remote=origin --push

NO hagas: análisis, gráficos, modelos, Docker, CI, dashboard.

Al terminar, para y presenta el CHECKPOINT.
```

---

# FASE 2 — EDA y el hallazgo de resolución

```
Fase 2. Lee CLAUDE.md, en especial §8.3.

OBJETIVO: el análisis exploratorio, y la demostración de que el dato público
diario no puede mostrar los episodios.

1. eda.py con funciones puras:
   - cobertura_por_estacion_y_anio(df): % de horas con valor
   - episodios(df, umbral): conteo por estación y año de horas >= umbral
   - resumen_anual(df): n, media, p99, máximo, horas >=350, horas >=500
   - ciclo_horario(df) y ciclo_estacional(df): ¿a qué hora y en qué mes
     ocurren los episodios? Es información operativa real.
2. LA VERIFICACIÓN CENTRAL — reconstruccion_diaria(df):
   promedia la serie horaria de los_maitenes a diaria y compárala con
   so2_diario.csv. Debe coincidir en 99,9 % de 9.427 días con diferencia
   mediana 0,000. Si no coincide, PARA: significa que la ingesta está mal.
   Este test es la prueba de que ambas series son el mismo dato.
3. comparacion_resolucion(df): en la misma estación y periodo, cuántas
   superaciones hay a resolución diaria (norma 24 h = 150) frente a cuántas
   horas de emergencia (>= 500) a resolución horaria. Los valores esperados
   están en CLAUDE.md §8.3.
4. CLI `caq eda` -> reports/eda.json + figuras.
5. Figuras en reports/figures/ (matplotlib, backend Agg, títulos y ejes en
   español, dos colores consistentes):
   - serie anual de horas en emergencia, las tres estaciones superpuestas
   - máximo anual por estación, con una línea vertical en 2023-05-31
   - LA FIGURA CLAVE: la misma semana de datos en 1995 dibujada dos veces —
     arriba la serie horaria con sus picos sobre 500, abajo el promedio diario
     de esa misma semana, plano y muy por debajo de la norma. Un pie de una
     línea: "mismo dato, dos resoluciones".
   - mapa de calor hora del día x mes de los episodios
   - cobertura de datos por estación y año
6. tests/test_eda.py contra los valores de CLAUDE.md §8.2 y §8.3.
7. README: sección "Los datos" y sección "Por qué el dato público no muestra
   los episodios", con la figura clave embebida.

Al terminar, para y presenta el CHECKPOINT.
```

---

# FASE 3 — La recuperación: puntos de quiebre y serie interrumpida

```
Fase 3. Lee CLAUDE.md §9.1. Esta fase es el corazón del repositorio.

OBJETIVO: medir qué cambió, cuándo, y decir con honestidad qué se puede y qué
no se puede atribuir al cierre de la fundición.

1. Añade `ruptures` a las dependencias.
2. recovery.py:
   - serie_mensual(df, estacion): media, p99, máximo y horas >=500 por mes.
   - puntos_de_quiebre(serie, n_bkps=None): PELT sobre la serie mensual, SIN
     pasarle la fecha del cierre. Devuelve las fechas detectadas.
     ESTA ES LA PRUEBA: si el método encuentra 2023 por su cuenta, el argumento
     se sostiene solo. Reporta TODOS los quiebres, no solo el que conviene.
   - serie_interrumpida(serie, fecha_corte): regresión segmentada con término
     de nivel y de pendiente antes y después, con intervalos de confianza y
     errores estándar robustos a autocorrelación (Newey-West).
   - Ejecuta lo mismo sobre las_palmas como contraste urbano.
3. tests/test_recovery.py:
   - sobre una serie sintética con un quiebre conocido, puntos_de_quiebre lo
     encuentra dentro de ±2 periodos
   - la serie interrumpida sobre datos sin quiebre da un coeficiente no
     significativo
   - test de regresión: las tres estaciones tienen 0 emergencias en 2020-2026
4. CLI `caq recovery` -> reports/recovery.json + figuras:
   - serie mensual con los quiebres detectados marcados
   - el ajuste de la serie interrumpida con su banda de confianza
   - comparación con las_palmas
5. README, sección "Qué cambió y qué podemos afirmar":
   - los quiebres que el método detectó, TODOS
   - la magnitud estimada del cambio con su intervalo
   - **y una subsección "Lo que esto NO demuestra"** con los confusores de
     CLAUDE.md §9.1: sin grupo de control no expuesto dentro de la bahía, sin
     meteorología para todo el periodo, 33 años con otros cambios regulatorios,
     y la pandemia solapada con parte del descenso. Es un estudio observacional
     sobre un evento real, no un ensayo controlado. Dilo así.

Al terminar, presenta el CHECKPOINT con los quiebres detectados y sus fechas.
```

---

# FASE 4 — Pronóstico horario con validación temporal

```
Fase 4. Lee CLAUDE.md §9.2 y la regla dura 1.

OBJETIVO: predecir el SO₂ de la hora siguiente, con validación estrictamente
temporal y una línea base que sea difícil de batir.

1. forecast.py:
   - construir_features(df): rezagos de SO₂ (1, 2, 3, 6, 12, 24 h), media móvil,
     hora del día y mes como seno/coseno, y meteorología.
   - CRÍTICO: la dirección del viento es CIRCULAR. Descomponla en sin(θ) y
     cos(θ). Un modelo que trate 359° y 1° como opuestos está roto. Añade un
     test que lo verifique explícitamente.
   - Usa la meteorología de puchuncavi (99 % de cobertura desde 2009), no la de
     la_greda (29 %).
   - modelo_persistencia(): la predicción es el valor de la hora anterior. Es la
     línea base obligatoria.
   - Zoo: persistencia, regresión lineal, random forest, gradient boosting.
2. Validación: TimeSeriesSplit o cortes por año. NUNCA aleatoria. Documenta en
   el docstring por qué, y añade un test que falle si alguien usa
   train_test_split sin shuffle=False.
3. Métricas: MAE, RMSE, y R² frente a la persistencia. Reporta SIEMPRE la
   persistencia en la primera fila de la tabla.
4. Analiza y reporta: ¿en qué régimen mejora el modelo a la persistencia?
   Probablemente en las horas de transición, no en las estables. Si el modelo
   NO le gana a la persistencia, dilo: es un resultado válido y frecuente en
   series horarias de contaminación.
5. Importancia de variables: ¿cuánto aporta la dirección del viento frente a los
   rezagos? Es la pregunta interesante del dominio.
6. tests/test_forecast.py:
   - test de circularidad del viento
   - test de fuga temporal: ningún fold de entrenamiento contiene timestamps
     posteriores a su fold de evaluación
   - la persistencia obtiene exactamente el MAE esperado sobre una serie
     sintética conocida
7. CLI `caq forecast` -> reports/forecast.json + figuras.
8. README: sección con la tabla de modelos (persistencia primero), y una frase
   honesta sobre cuánto se gana realmente.

Al terminar, presenta el CHECKPOINT con la tabla de modelos.
```

---

# FASE 5 — Docker, CI, dashboard y publicación

```
Fase 5. Lee CLAUDE.md §14.7. Última fase. Presenta un CHECKPOINT intermedio
al terminar el bloque A.

BLOQUE A — Informe y dashboard
1. report.py: informe HTML autocontenido con jinja2, CSS embebido, figuras en
   base64, cero dependencias de red.
2. app/streamlit_app.py con pestañas:
   - Contexto: qué es Quintero-Puchuncaví, la norma, el cierre de 2023
   - Episodios: línea de tiempo de horas en emergencia por estación, con los
     hitos marcados (2011 La Greda, 2018 Quintero, 2023 cierre); selector de
     estación y de umbral
   - Resolución: la comparación diario-vs-horario, interactiva: el usuario
     elige una semana y ve las dos series
   - Recuperación: los quiebres detectados y el ajuste de serie interrumpida
   - Pronóstico: la tabla de modelos y el error frente a la persistencia
   - Límites: qué NO demuestra este análisis
   Lee de reports/*.json, no recalcula nada al arrancar.
3. Prueba el dashboard con `uv run streamlit run app/streamlit_app.py`. NO uses
   el navegador automatizado: la verificación visual la hace la usuaria.

--- CHECKPOINT INTERMEDIO ---

BLOQUE B — Empaquetado
4. Dockerfile multi-stage. `uv sync --frozen --no-dev --no-editable` (CLAUDE.md
   §14.7). .dockerignore agresivo. docker-compose.yml con pipeline y dashboard.
   NO ejecutes docker: esta máquina no lo tiene.
5. .github/workflows/ci.yml: lint + tests en Python 3.11 y 3.12; job docker que
   construye la imagen Y ejecuta el pipeline dentro del contenedor (no solo
   `version`); job que ejecuta el pipeline completo y verifica los JSON.
   Usa las versiones actuales de las actions (actions/checkout@v7,
   astral-sh/setup-uv@v10.1.0) para no arrastrar el aviso de Node 20.
6. .github/workflows/pages.yml que publique el informe HTML. Activa Pages en
   Settings antes del primer push, o el workflow falla.
7. .streamlit/config.toml y requirements.txt para Streamlit Community Cloud.
8. README final:
   1. Título + badges + una frase del problema
   2. Enlaces arriba: dashboard, informe, y un aviso de que la app gratuita de
      Streamlit se duerme tras varios días sin visitas
   3. El resultado principal en la primera pantalla: la tabla de emergencias
      por periodo, y la figura de las dos resoluciones
   4. "Por qué el dato público no muestra los episodios"
   5. "Qué cambió tras el cierre" y "Lo que esto NO demuestra"
   6. Quickstart, estructura, decisiones de diseño, limitaciones, fuentes
   9. Autor: @ajmedinaa-gif
   REGLA: ningún número escrito a mano. Test de correspondencia README↔JSON.
9. CONTRIBUTING.md documentando las 5 fases.
10. Revisión final: make all en verde, CI en verde, cobertura >= 80 %,
    sin secretos versionados, y data/raw/ efectivamente fuera del repo.

Al terminar, presenta el CHECKPOINT final.
```
