# Épica 1 — Datos confiables y visibles de MovieLens 32M

**Objetivo de la épica:** que el equipo entrene y analice recomendadores solo con datos validados,
limpios y versionados, y que cualquiera pueda entender esos datos sin correr notebooks.

**Dataset:** MovieLens 32M (`../ml-32m`): 32.000.204 ratings, 200.948 usuarios, 87.585 películas,
1995-01-09 → 2023-10-13. Escala oficial 0,5–5,0 en medias estrellas.

Estados: ✅ Hecho (cumple DoD) · 🟡 Hecho, falta revisión del par / demo · ⬜ Pendiente

---

## US1.3 — Datos controlados y filtrados con los umbrales del EDA

> **As an** Analyst, **I want** the data to be checked and filtered automatically with the EDA thresholds
> **so that** the model is only trained with valid and useful data.

### Criterios de aceptación

| # | Dado / Cuando / Entonces | Verificado por |
|---|---|---|
| AC1 | **Dado** un dataset con valores faltantes, notas fuera de escala, ratings repetidos o IDs que no existen en otra tabla, **cuando** corre el pipeline, **entonces** se detiene antes de generar datos limpios | `test_checks.py` (un ejemplo pequeño por problema), `test_ac1_*` |
| AC2 | **Dado** que un control falla, **entonces** el mensaje dice qué control, en qué tabla, cuántas filas, qué se esperaba, muestra ejemplos y dónde ver el detalle | `test_ac1_ac2_valor_faltante_detiene_con_mensaje_claro`, corrida real (abajo) |
| AC3 | **Dado** `data.min_ratings` en `params.yaml`, **cuando** corre `clean`, **entonces** se eliminan los usuarios y películas bajo el umbral y los datos limpios quedan versionados en DVC | `test_ac3_ac4_camino_feliz`, `dvc.lock` |
| AC4 | **Dado** una ejecución, **entonces** queda un informe corto con los problemas que encontró cada control y los ratings eliminados | `reports/clean_report.md`, `test_ac3_ac4_camino_feliz` |

### Tareas

#### US1.3 t1 — Controles básicos que detienen el pipeline · 2 h · 🟡

Agrega controles al inicio del pipeline. Si uno falla, el pipeline se detiene con un mensaje claro que dice qué está
mal. Cubre AC1 y AC2 (incluye las antiguas tareas 1 y 2 de US1.2).

| Checklist | Implementación |
|---|---|
| ✅ Valores faltantes en cada columna de users, movies y ratings | 11 controles `<tabla>_<columna>_missing` (NULL o texto vacío). `users` se deriva de ratings (D-09) |
| ✅ Ratings fuera de escala | `ratings_rating_range` (límites en `validation.rating_min/max`) y `ratings_rating_step` · ver D-01 |
| ✅ Ratings repetidos usuario–película | `ratings_unique_pair`, más `movies_unique_id` y `users_unique_id` |
| ✅ IDs de usuario y película que no existen en las otras tablas | `ratings_orphan_movie`, `ratings_orphan_user`, `tags_orphan_movie`, `tags_orphan_user`, `links_orphan_movie` |
| ✅ El pipeline se detiene con un mensaje claro | etapa `validate`: exit 1 y DVC no corre `clean`; mensaje en `reporting.print_results` |
| ✅ Tests con ejemplos pequeños con problemas conocidos | `tests/test_checks.py` (26 casos) y `tests/test_pipeline_gate.py` (5 casos de punta a punta) |

#### US1.3 t2 — Aplicar los umbrales del EDA desde params.yaml y guardar los datos limpios con DVC · 2 h · 🟡

Aplica el mínimo de ratings recomendado por el EDA (k ≥ 10), leído de `params.yaml`, y guarda los datos limpios con
su versión en DVC. Cada ejecución deja un informe corto. Cubre AC3 y AC4 (incluye la antigua tarea 3 de US1.2).

| Checklist | Implementación |
|---|---|
| ✅ `data.min_ratings` en params.yaml (separado de `serving.min_ratings`) | `data.min_ratings: 10` (limpieza) y `serving.min_ratings: 50` (rankings, D-10) |
| ✅ Se eliminan usuarios y películas bajo el umbral | etapa `clean`, filtro iterativo hasta que todos cumplen (D-02) y post-condición |
| ✅ Datos limpios guardados y versionados con DVC | `data/processed/` es salida de DVC; su hash queda en `dvc.lock` |
| ✅ Informe corto: problemas por control y ratings eliminados | `reports/clean_report.md` + `reports/metrics/clean.json` (`dvc metrics show`) |
| ✅ README: cómo correr la limpieza | sección «Limpieza de datos (US1.3 t2)» y `make clean-data` |

---

## US1.5 — Dashboard visual de ratings y calidad

> **As an** Analyst, **I want** a visual dashboard of the ratings and the data quality **so that** the team can
> understand the data without running notebooks.

### Criterios de aceptación

| # | Dado / Cuando / Entonces | Verificado por |
|---|---|---|
| AC1 | **Dado** un clon del repo con el dataset en `../ml-32m`, **cuando** ejecuto `make dashboard`, **entonces** se instala el entorno, se actualizan los datos y el dashboard abre en `:8501` | corrida real (abajo) |
| AC2 | **Dado** el dashboard, **entonces** veo la distribución y evolución de las notas, la popularidad y la dispersión, con los mismos cálculos del notebook EDA | páginas *Resumen*, *Calificaciones* y *Popularidad y dispersión*; `test_eda.py` |
| AC3 | **Dado** que un control de US1.3 falla, **entonces** el estado lo indica y *Calidad de datos* muestra el control, su severidad, las filas afectadas y ejemplos, aunque el pipeline se haya detenido | página *Calidad de datos* |
| AC4 | **Dado** un filtro de umbral, género, año o nota, **entonces** los gráficos se recalculan sobre esa selección | `test_eda.py::test_filtro_*`, `test_dashboard.py` |
| AC5 | **Dado** un integrante nuevo, **cuando** lee el README, **entonces** sabe arrancar, leer el panel y cambiar una regla | `README.md` |

### Tareas

| Tarea | Estimado | Estado | Entregable |
|---|---|---|---|
| **US1.5 t1** — Gráficos de ratings y sparsity (reutilizando el notebook del EDA) | 2 h | 🟡 | consultas compartidas en `eda.py`; páginas *Resumen*, *Calificaciones*, *Popularidad y dispersión*; exploración de usuarios, películas y grafo de gustos; informe `notebooks/01_eda_ratings.ipynb` |
| **US1.5 t2** — Panel de calidad con los controles de US1.3 | 2 h | 🟡 | página *Calidad de datos*: checklist de US1.3 t1, detalle filtrable con ejemplos, limpieza de US1.3 t2 y descarga del informe |
| **US1.5 t3** — Filtros de umbral y género, arranque con un comando y README | 2 h | 🟡 | barra lateral (datos, umbral, géneros, años, notas), `make dashboard`, `README.md` |

---

## Definition of Done

- [x] Código en `src/` con docstring que cita la historia/tarea.
- [x] `make test` pasa (los AC están codificados como tests).
- [x] `make pipeline` termina y un segundo `dvc repro` dice *up to date* (reproducible).
- [x] Reglas y umbrales en `params.yaml`, sin números mágicos en el código.
- [x] Métricas en `reports/metrics/` (visibles con `dvc metrics show`) y `dvc.lock` actualizado.
- [x] README y `docs/DECISIONS.md` actualizados.
- [ ] Commit(s) que citan la tarea, `dvc.lock` + `reports/` en el mismo commit que el código.
- [ ] Revisión de un par (PR) y demo al PO.

Las tareas quedan en 🟡 hasta el commit, la revisión del par y la demo: los demás ítems ya se cumplen.

---

## Evidencia del incremento

Corrida del 2026-11-25 sobre ML-32M (servidor del laboratorio, Python 3.12). `make pipeline` completo: 3 min.

### US1.3

| Etapa | Resultado |
|---|---|
| `ingest` | 12/12 controles de archivos pasan (existencia, MD5 contra `checksums.txt`, esquema); escribe 6 tablas Parquet, incluida `users` |
| `validate` | 25/25 controles de contenido pasan (24 bloqueantes, 1 aviso) |
| `clean` | umbral 10; converge en 3 iteraciones; escribe `reports/clean_report.md` |
| `profile` | sensibilidad para umbrales 1, 5, 10, 20, 30, 50 y 100 |

| | Antes | Después | Eliminados |
|---|---:|---:|---:|
| Ratings | 32.000.204 | 31.842.696 | 157.508 (0,49%) |
| Usuarios | 200.948 | 200.947 | 1 |
| Películas | 84.432 | 31.961 | 52.471 (62,15%) |
| Densidad | 0,189% | 0,496% | ×2,6 |

- **AC1 y AC2 (datos reales):** con la regla literal 1–5 (`rating_min: 1.0`), `validate` termina con exit 1 y este mensaje:

  ```text
  >> PIPELINE DETENIDO en 'validate': 1 control(es) bloqueante(s) fallaron.
     - Notas dentro de la escala [1.0, 5.0] [ratings]: 525.132 filas. Se esperaba: 1.0 ≤ rating ≤ 5.0.
         ejemplo: {'userId': 3, 'movieId': 141, 'rating': 0.5, 'timestamp': 1084484791}
     Detalle: reports/quality/checks.json · Panel: `make dashboard` → Calidad de datos.
  ```

  Por eso la escala vigente es 0,5–5,0 (D-01, aprobada el 2026-11-25).
- **AC1 (tests):** un ejemplo pequeño por problema conocido: 10 columnas con valores faltantes, 4 notas fuera de
  escala, la regla literal 1–5, duplicados, 5 tipos de IDs inexistentes, CSV truncado y tipos inválidos.
- **AC3:** con `data.min_ratings: 20`, `dvc status` marcó solo `clean` y `dvc repro` saltó `ingest`, `validate` y
  `profile` (1 min; 31.722.400 ratings). Al volver a 10, solo se recalculó `clean` (~50 s).
- **AC4:** `reports/clean_report.md` lista los 37 controles con sus problemas, los eliminados y cada iteración.

### US1.5

- **AC1:** `make dashboard` crea el entorno, ejecuta `dvc repro` y levanta Streamlit en el puerto 8501.
  Desde un servidor remoto, ver el túnel SSH del README.
- **AC2:** 7 páginas en 3 secciones:
  - **Análisis:** Resumen, Calificaciones, y Popularidad y dispersión.
  - **Exploración:** Usuarios y películas, y Grafo de gustos.
  - **Datos:** Calidad de datos y Pipeline.

  Las consultas son las de `eda.py`, las mismas del notebook.
- **AC3:** franja de estado (al día / con avisos / detenido / validación desactualizada). La página de calidad tiene
  el checklist de US1.3 t1 y el detalle filtrable con ejemplos.
- **AC4:** `tests/test_dashboard.py` abre las 7 páginas con `AppTest` y comprueba que el umbral (100) más un género
  (Comedy) reducen los ratings.
- **Tests:** `make test` → 51 pasan.

### Hallazgos del EDA (para la demo)

- 31,3% de los ratings usan media estrella; la moda es 4,0 (26,1%) y la media 3,54.
- El 62% de las películas con ratings tiene menos de 10; el 10% más popular concentra el 95,7% de los ratings.
- El umbral 10 cuesta 0,5% de los ratings y ningún usuario relevante, pero deja fuera el 62% del catálogo:
  conviene acordar con el PO si las películas del long tail importan para el producto.
- Las películas populares reciben mejores notas (ρ = 0,25). En el grafo de gustos, las vecinas de *The Matrix* son
  *Fight Club*, *El Señor de los Anillos* y *Star Wars V*.

### Pendientes para cerrar las tareas

- [ ] Commits por tarea y PR (el repo está inicializado, sin commits).
- [x] Escala de notas 0,5–5,0 aprobada (D-01).
- [ ] Revisión de un par y demo al PO; validar D-10 (`serving.min_ratings = 50`).
- [ ] Remoto DVC compartido (`dvc remote add -d …`) para que el equipo haga `dvc pull` en vez de recalcular.
