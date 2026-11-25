# Épica 1 — Datos confiables y visibles de MovieLens 32M

Pipeline reproducible (DVC) que **valida** y **limpia** los ratings de MovieLens 32M, más un
**dashboard** (Streamlit) para que todo el equipo entienda los datos y su calidad sin abrir notebooks.

| Historia | Qué entrega | Dónde |
|---|---|---|
| **US1.3** Datos controlados y filtrados con los umbrales del EDA | Controles que detienen el pipeline con un mensaje claro · umbral `data.min_ratings` · datos limpios en DVC · informe corto por ejecución | `dvc.yaml`, `src/movielens/{ingest,checks,validate,kcore,clean}.py` |
| **US1.5** Dashboard visual | Ratings, popularidad y dispersión · explorador de usuarios y películas · grafo de gustos · panel de calidad · filtros de umbral y género · arranque en un comando · informe EDA | `app/`, `src/movielens/{eda,explore,charts,report}.py`, `notebooks/` |

Historias, criterios de aceptación, Definition of Done y evidencia: [`docs/BACKLOG.md`](docs/BACKLOG.md).
Decisiones tomadas y por qué: [`docs/DECISIONS.md`](docs/DECISIONS.md).
Publicar el dashboard en Streamlit Community Cloud: [`docs/DEPLOY.md`](docs/DEPLOY.md).

---

## Ejecutar en local

### Requisitos

- **Python 3.11 o 3.12** (probado con 3.12). En Windows, el instalador de python.org.
- **git**. DVC lo necesita; si la carpeta no es un repositorio, el arranque lo inicializa.
- **Espacio y memoria:** unos 3 GB libres en disco y 8 GB de RAM.
- **Dataset:** solo hace falta para correr el pipeline. Si tu copia del proyecto ya trae `data/processed/`, puedes
  abrir el dashboard sin él.

### Opción A: abrir el dashboard con los datos ya procesados (lo más rápido)

Usa el paquete que trae la carpeta `data/` (`Epic_1_con_datos.zip`):

```bash
# 1. Descomprime el .zip y entra en la carpeta
cd Epic_1

# 2. Arranca (crea el entorno la primera vez, unos minutos)
python run_local.py          # Windows: py -3.12 run_local.py
```

El navegador se abre solo en <http://localhost:8501>. Para detenerlo: `Ctrl+C` en la terminal.

### Opción B: reproducir todo desde el dataset crudo

1. Descarga MovieLens 32M de <https://files.grouplens.org/datasets/movielens/ml-32m.zip> (≈ 240 MB) y descomprímelo
   **al lado** de `Epic_1/`:

   ```text
   mi-carpeta/
   ├── Epic_1/
   └── ml-32m/        ratings.csv, movies.csv, tags.csv, links.csv, checksums.txt
   ```

   Si lo guardas en otra ruta, cámbiala en `params.yaml → data.raw_dir`.
2. Arranca con `python run_local.py` (o `make dashboard` en Linux/macOS). La primera vez el pipeline valida y limpia
   los 32 millones de ratings (3 a 5 minutos). Las siguientes veces solo se recalcula lo que cambió.

### Comandos equivalentes, paso a paso

Para quien prefiera no usar `run_local.py`:

```bash
# Linux / macOS
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -e .
git init -q                       # solo si la carpeta no es un repositorio
dvc repro                         # pipeline (omitir si usas los datos ya procesados)
streamlit run app/dashboard.py
```

```powershell
# Windows (PowerShell)
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -e .
git init -q
.venv\Scripts\python -m dvc repro
.venv\Scripts\python -m streamlit run app/dashboard.py
```

### Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `Se necesita Python 3.11 o superior` | Instala Python 3.12 y ejecuta con él (`py -3.12 run_local.py` en Windows) |
| El puerto 8501 está ocupado | `python run_local.py --port 8600` |
| `dvc` dice que no es un repositorio git | `git init` dentro de `Epic_1/` |
| Falta memoria al correr el pipeline | Antes de arrancar: `EPIC1_DUCKDB_MEMORY=2GB` (Windows: `$env:EPIC1_DUCKDB_MEMORY="2GB"`) |
| El pipeline se detiene | Es intencional si un control de calidad falla: el motivo aparece en la terminal y en *Calidad de datos* |

### En el servidor del laboratorio

El dashboard corre en el servidor, así que `localhost:8501` en tu navegador no lo encuentra hasta reenviar el puerto:

- **Túnel SSH (lo más confiable):** en una terminal **de tu computador** (no la del servidor), deja corriendo
  `ssh -N -L 8501:localhost:8501 -p <puerto-ssh> <usuario>@<servidor>` y abre <http://localhost:8501>.
  Si el 8501 de tu computador está ocupado, usa `-L 8600:localhost:8501` y abre <http://localhost:8600>.
- **VS Code (Remote-SSH):** al correr `make dashboard` en la terminal de VS Code, el navegador debería abrirse solo.
  Si no se abre: pestaña **Ports** → **Forward a Port** → `8501`, y usa la dirección de la columna *Forwarded Address*.
- **Disco NFS lento:** la primera instalación puede tardar varios minutos; para hacerla en disco local usa
  `make dashboard VENV=/tmp/epic1-venv`.
- **`ulimit -v` de 16 GB del grupo `@ialab`:** el `Makefile` ya limita los hilos de OpenBLAS y DuckDB, y DuckDB está
  fijado en `< 2` (ver D-07). Si corres `dvc repro` o `streamlit` a mano, usa antes `export OPENBLAS_NUM_THREADS=4`.

Si un control bloqueante falla, el pipeline se detiene **pero el dashboard abre igual** y muestra la causa en la página
*Calidad de datos*; los gráficos siguen mostrando los últimos datos limpios aprobados.

### Otros comandos

```text
make help        lista de comandos
make pipeline    todo el pipeline (dvc repro)
make clean-data  controles + limpieza por umbral e informe corto (dvc repro clean)
make test        51 tests: controles con ejemplos de problemas conocidos, limpieza, consultas, dashboard
make eda         ejecuta el notebook de EDA y guarda sus gráficos (abrirlo luego en VS Code/Jupyter)
make eda-check   ejecuta el notebook de EDA de punta a punta sin modificarlo (para CI)
make metrics     métricas de calidad y limpieza (dvc metrics show)
make status      ¿datos al día con el código y los parámetros? (dvc status)
```

---

## Qué muestra el dashboard

| Sección | Página | Contenido | Tarea |
|---|---|---|---|
| Análisis | **Resumen** | Indicadores clave, estado del pipeline, distribución de notas, ratings por año y género, películas destacadas, limpieza aplicada | US1.5 t1 |
| | **Calificaciones** | Escala y uso de cada nota por año, nota media por usuario y por película, usuarios nuevos y recurrentes, nota media por año, géneros y décadas de estreno | US1.5 t1 |
| | **Popularidad y dispersión** | Distribución de la actividad (log-log), curvas de Lorenz y Gini, popularidad frente a nota, rankings, densidad por bloques de la matriz, efecto del umbral | US1.5 t1 |
| Exploración | **Usuarios y películas** | Un usuario: sus reacciones en el tiempo, afinidad por género y usuarios con gustos parecidos (grafo usuario–película). Una película: su audiencia, notas por año y películas similares | US1.5 t1 |
| | **Grafo de gustos** | Películas conectadas cuando les gustan a las mismas personas, con fuerzas tipo Obsidian, búsqueda y resaltado de vecinos | US1.5 t1 |
| Datos | **Calidad de datos** | Checklist de US1.3 t1, detalle de cada control con ejemplos, resultado de la limpieza de US1.3 t2 y descarga del informe | US1.5 t2 |
| | **Pipeline** | Etapas DVC, `params.yaml` vigente, comandos y `dvc status` | US1.5 t3 |

**Filtros** (barra lateral, US1.5 t3):

- **Datos:** *Limpios* o *Validados*.
- **Umbral mínimo de ratings:** solo usuarios y películas con al menos N ratings.
- **Géneros, años y rango de notas.**

Aplican a las páginas de análisis y al grafo. Calidad, Pipeline y el explorador muestran siempre los datos completos.

Una reacción es la nota de un usuario a una película: *le gustó* (≥ 4), *neutral* o *no le gustó* (≤ 2). Dos películas
son similares cuando les gustan a las mismas personas (coseno, ver D-11).

---

## Pipeline

```text
../ml-32m/*.csv ──▶ ingest ──▶ validate ──▶ clean ───▶ data/processed/ + reports/clean_report.md
                                   └──────▶ profile ─▶ reports/profile/kcore_sweep.csv
```

| Etapa | Tarea | Qué hace | Si falla |
|---|---|---|---|
| `ingest` | US1.3 t1 | Verifica el MD5 contra `checksums.txt`, parsea los CSV con esquema estricto, escribe Parquet en `data/interim/` y deriva la tabla `users` | exit 1: archivo faltante, truncado o con tipos inválidos |
| `validate` | US1.3 t1 | Corre los controles de contenido (abajo) y escribe `reports/quality/checks.json` | exit 1 si algún control **bloqueante** falla |
| `clean` | US1.3 t2 | Elimina usuarios y películas con menos de `data.min_ratings` ratings; guarda `data/processed/` y el informe | exit 1 si la validación no está aprobada o el resultado no cumple el umbral |
| `profile` | US1.5 t1 | Densidad y cobertura para cada umbral de `profile.k_values` | — |

### Controles de calidad (US1.3 t1)

| Checklist | Controles | Severidad |
|---|---|---|
| Valores faltantes en cada columna de users, movies y ratings | `<tabla>_<columna>_missing` (11 controles: NULL o texto vacío) | Bloqueante |
| Ratings fuera de escala | `ratings_rating_range` (`validation.rating_min/max`, 0,5–5,0, ver D-01), `ratings_rating_step` | Bloqueante |
| Ratings repetidos usuario–película | `ratings_unique_pair`; además `movies_unique_id`, `users_unique_id` | Bloqueante |
| IDs que no existen en las otras tablas | `ratings_orphan_movie`, `ratings_orphan_user`, `tags_orphan_movie`, `tags_orphan_user`, `links_orphan_movie` | Bloqueante |
| Archivos íntegros y con el esquema esperado | `*_file_exists`, `*_md5`, `*_parse`, `*_schema` | Bloqueante |
| Fechas plausibles | `ratings_timestamp_range` (entre `validation.min_date` y hoy) | Aviso |

Cada regla es una consulta SQL legible en [`src/movielens/checks.py`](src/movielens/checks.py) que devuelve las filas
que la violan. MovieLens 32M no trae un archivo de usuarios: `users` se deriva de `ratings` (D-09). Para cambiar la
severidad de un control sin tocar código: `validation.severity_overrides` en `params.yaml`.

Si un control bloqueante falla, el pipeline se detiene con un mensaje como este:

```text
>> PIPELINE DETENIDO en 'validate': 1 control(es) bloqueante(s) fallaron.
   - Notas dentro de la escala [1.0, 5.0] [ratings]: 525.132 filas. Se esperaba: 1.0 ≤ rating ≤ 5.0.
       ejemplo: {'userId': 3, 'movieId': 141, 'rating': 0.5, 'timestamp': 1084484791}
   Detalle: reports/quality/checks.json · Panel: `make dashboard` → Calidad de datos.
```

### Limpieza de datos (US1.3 t2)

```bash
make clean-data        # = dvc repro clean: ingest → validate → clean (solo lo que cambió)
cat reports/clean_report.md
dvc metrics show       # ratings, usuarios y películas antes/después
```

- **Umbral:** `data.min_ratings` en `params.yaml` (hoy 10, el valor que recomienda el EDA). Se aplica a usuarios y
  películas, repitiendo el filtro hasta que todos cumplen.
- **Rankings:** `serving.min_ratings` (hoy 50) es otro parámetro. Solo define qué películas aparecen en rankings y
  recomendaciones; no cambia los datos limpios.
- **Salida:** `data/processed/{ratings,movies,movie_genres,users}.parquet`, versionada por DVC (hash en `dvc.lock`).
- **Informe corto de cada ejecución:** `reports/clean_report.md`, con los problemas que encontró cada control y los
  ratings, usuarios y películas eliminados.

Para cambiar el umbral:

```bash
sed -i 's/^  min_ratings: 10 /  min_ratings: 20 /' params.yaml   # data.min_ratings
make clean-data        # DVC vuelve a correr solo `clean`
dvc metrics diff       # compara contra el último commit
```

### Versionado de datos

- `dvc.lock` guarda el hash de cada entrada y salida: un commit de git identifica exactamente qué datos limpios lo acompañan.
- Los CSV crudos **no se copian** al repo: son una dependencia externa cuyo MD5 queda en `dvc.lock` (D-03).
- Los reportes (`reports/`) van a git (`cache: false`), así el historial de calidad queda en el log del repo.
- **Pendiente del equipo:** definir un remoto compartido (`dvc remote add -d storage <ruta|s3://…>`) para `dvc push` / `dvc pull`.

---

## Estructura

```text
Epic_1/
├── run_local.py             # arranque local en un comando (Windows, macOS, Linux)
├── Makefile                 # make dashboard / pipeline / test … (Linux, macOS)
├── params.yaml              # todas las reglas (escala, data.min_ratings, serving.min_ratings, rutas)
├── dvc.yaml · dvc.lock      # pipeline y versiones de datos
├── requirements.in/.txt     # dependencias directas / fijadas
├── src/movielens/
│   ├── ingest.py            # US1.3 t1: integridad + CSV → Parquet
│   ├── checks.py            # US1.3 t1: reglas de calidad (SQL)
│   ├── validate.py          # US1.3 t1: gate que detiene el pipeline
│   ├── kcore.py · clean.py  # US1.3 t2: umbral, datos limpios e informe corto
│   ├── profile.py           # US1.5 t1: sensibilidad del umbral
│   ├── eda.py               # US1.5 t1: consultas del EDA (notebook + dashboard)
│   ├── explore.py           # US1.5 t1: explorador de usuarios/películas y grafo de gustos
│   ├── charts.py            # US1.5 t1: gráficos interactivos del dashboard (plotly)
│   ├── report.py            # US1.5 t1: figuras y tablas del informe EDA (matplotlib)
│   └── reporting.py         # formato común de reportes de calidad
├── app/
│   ├── dashboard.py         # US1.5: navegación y filtros (Streamlit)
│   ├── common.py · graph.py # datos/caché/estilo · grafo interactivo (vis-network en app/static/)
│   ├── bootstrap.py         # src/ importable, secretos y descarga de datos (Community Cloud)
│   ├── requirements.txt     # dependencias solo del dashboard (Community Cloud)
│   └── views/               # una página por archivo
├── notebooks/01_eda_ratings.ipynb   # informe EDA formal: 13 figuras, 5 tablas, conclusiones
├── tests/                   # criterios de aceptación como tests
├── reports/                 # quality/, metrics/, profile/, clean_report.md (versionados en git)
├── data/                    # interim/, processed/ (gestionados por DVC)
└── docs/                    # BACKLOG.md (historias, AC, DoD) · DECISIONS.md · DEPLOY.md
```

## Cómo trabajamos (Agile Data)

- **Una tarea = un incremento demostrable**: cada tarea del backlog deja algo que se puede ver en el dashboard o en `dvc metrics`.
- **Criterios de aceptación como tests**: `tests/test_pipeline_gate.py` codifica los AC de US1.3; `make test` debe pasar antes de cerrar una tarea.
- **Reglas en `params.yaml`, no en el código**: el PO puede ajustar umbrales y ver el impacto con `dvc metrics diff`.
- **Decisiones registradas** en `docs/DECISIONS.md` con su evidencia y cómo revertirlas.
- **Flujo git sugerido:** una rama por tarea (`us1.3-t1-checks`), commits que citan la tarea (`US1.3 t1: …`), PR con revisión de un par, y `dvc.lock` + `reports/` dentro del mismo commit que el código que los produjo.
