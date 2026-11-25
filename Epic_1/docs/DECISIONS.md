# Registro de decisiones — Épica 1

Formato corto: contexto → decisión → evidencia → cómo revertir. Cualquier integrante puede proponer
cambios; el PO valida las que afectan reglas de negocio (D-01, D-02, D-05, D-10).

---

### D-01 · Escala de notas válida: 0,5–5,0 en pasos de 0,5 (no 1–5)

- **Contexto:** el checklist de US1.3 t1 dice "Ratings outside 1–5". El README oficial de ML-32M dice: *"5-star scale,
  with half-star increments (0.5 stars - 5.0 stars)"*.
- **Decisión:** el check `ratings_rating_range` usa `[0,5, 5,0]` y `ratings_rating_step` exige múltiplos de 0,5.
- **Evidencia:** 525.132 ratings (1,64%) valen 0,5 y 31,3% usan media estrella. Prueba real del 2026-11-25 con
  `rating_min: 1.0`: `validate` falló (`ratings_rating_range`, 525.132 filas), `dvc repro` terminó con error y `clean`
  no corrió. El panel de calidad mostró el fallo con ejemplos de filas.
- **Cómo revertir:** `validation.rating_min: 1.0` en `params.yaml`. Ojo: con los datos actuales eso **detiene el
  pipeline** (los ratings de 0,5 son legítimos); si el negocio quiere excluirlos, debe ser una regla de *limpieza*
  en `clean`, no un check bloqueante.
- **Estado:** **aprobada** el 2026-11-25: el rango válido es 0,5–5,0.

### D-02 · Umbral único `data.min_ratings = 10`, aplicado como k-core iterativo

- **Contexto:** US1.3 t2 pide aplicar el mínimo recomendado por el EDA (k ≥ 10) leído de `data.min_ratings`,
  separado de `serving.min_ratings`. El mismo umbral vale para usuarios y películas. Un filtro de una sola pasada puede dejar usuarios bajo k al quitar películas (y viceversa).
- **Decisión:** k-core iterativo hasta convergencia (`clean.iterative: true`) y post-condición que aborta si el resultado no cumple k.
- **Evidencia (datos reales, k = 10):** una sola pasada deja 1 usuario con 9 ratings, lo que viola el contrato;
  la versión iterativa converge en 3 iteraciones y lo elimina (−9 ratings). En datos sintéticos el caso se reproduce en
  `tests/test_kcore.py::test_una_pasada_puede_violar_k`.
- **Cómo revertir:** `clean.iterative: false` (sólo con fines comparativos).

### D-03 · Los CSV crudos quedan fuera del repo, como dependencia externa de DVC

- **Contexto:** `../ml-32m` pesa ~1 GB; copiarlo al repo y a la caché de DVC lo triplicaría.
- **Decisión:** `ingest` declara los CSV como dependencias (su MD5 queda en `dvc.lock`) y además verifica los MD5
  publicados en `checksums.txt`. La ruta se configura en `data.raw_dir`.
- **Evidencia:** durante el desarrollo `ratings.csv` todavía se estaba copiando; el check `ratings_md5` es justamente
  lo que evita procesar un archivo truncado.
- **Cómo revertir:** mover el dataset a `data/raw/` y hacer `dvc add data/raw`.

### D-04 · Parquet + DuckDB para el dashboard

- **Contexto:** 32M filas no caben cómodamente en la memoria de una sesión de Streamlit por usuario.
- **Decisión:** Parquet tipado (zstd) y consultas DuckDB directas sobre los archivos, cacheadas por combinación de filtros.
- **Evidencia:** KPIs sobre 32M filas en ~1,7 s sin caché; cada cambio de filtro recalcula toda la página en ~3 s
  (medido con `streamlit.testing.AppTest`).

### D-05 · Todos los controles de US1.3 t1 son bloqueantes (reemplaza la versión anterior)

- **Contexto:** la versión anterior trataba los IDs huérfanos de `tags`/`links` como aviso. El checklist actualizado
  pide que el pipeline se detenga ante IDs de usuario o película que no existen en las otras tablas.
- **Decisión:** valores faltantes, escala, repetidos e IDs inexistentes (en ratings, tags y links) son **bloqueantes**.
  Solo las fechas fuera de rango quedan como aviso.
- **Evidencia:** con los datos reales los 37 controles pasan, así que endurecerlos no detiene el pipeline.
- **Cómo revertir:** `validation.severity_overrides: {tags_orphan_movie: warning}` en `params.yaml`, sin tocar código.

### D-06 · El notebook de EDA y el dashboard comparten código

- **Contexto:** US1.5 t1 pide reutilizar el notebook del EDA; en el repo no existía un notebook previo.
- **Decisión:** las **consultas** viven en `src/movielens/eda.py` y las usan tanto el notebook como el dashboard, así que
  los números siempre coinciden. La **presentación** se separa según el medio:
  - El dashboard usa plotly interactivo (`src/movielens/charts.py`), con filtros y tooltips.
  - El notebook es un informe formal con figuras estáticas de matplotlib (`src/movielens/report.py`). Se ven igual con el
    tema claro u oscuro de VS Code, en GitHub y al exportar a PDF. Antes usaba plotly, que con el tema oscuro de VS Code
    dejaba el texto ilegible.

  Si el equipo tiene un notebook EDA anterior, sus consultas se migran a `eda.py`.
- **Cómo verificar:** `make eda` ejecuta el notebook y guarda las figuras; `make eda-check` lo ejecuta sin modificarlo.
  `tests/test_eda.py` construye todas las figuras de ambos medios.

### D-07 · DuckDB < 2 y pocos hilos, por el límite de memoria virtual del servidor

- **Contexto:** el grupo `@ialab` tiene `ulimit -v` de 16 GB (soft) / 20 GB (hard) en `/etc/security/limits.conf`.
  DuckDB 2.0.1 reserva todo ese espacio de direcciones al conectarse: la segunda conexión falla con
  `OutOfMemoryException` aun con datos pequeños. Además, numpy con OpenBLAS a 48 hilos reserva ~2 GB virtuales al importarse.
- **Decisión:** `duckdb>=1.1,<2` en `requirements.in` (1.5.6 probado); conexiones con hilos y memoria acotados
  (`EPIC1_DUCKDB_THREADS`, `EPIC1_DUCKDB_MEMORY`); el `Makefile` fija `OPENBLAS_NUM_THREADS=4`.
- **Cómo revertir:** cuando DuckDB 2.x respete el límite (o en máquinas sin `ulimit -v`), subir el pin y verificar con `make test`.

### D-08 · El gate de `clean` y `profile` es `reports/metrics/quality.json`

- **Contexto:** `checks.json` incluye la hora de generación; usarlo como dependencia hacía que cada re-validación
  re-ejecutara `clean` y `profile` aunque nada material cambiara.
- **Decisión:** el *gate* es `quality.json` (conteos sin timestamp). `clean` además verifica `blocking_failed == 0`
  antes de escribir (defensa en profundidad).
- **Evidencia:** `dvc repro -f -s validate` re-valida y `profile` no se vuelve a ejecutar.
- **Actualización (US1.3 t2):** `clean` ahora también depende de `integrity.json` y `checks.json`, porque su informe
  corto (`reports/clean_report.md`) resume los problemas de cada control. Costo: forzar `validate` vuelve a correr
  `clean` (~40 s).

### D-09 · La tabla `users` se deriva de `ratings`

- **Contexto:** el checklist pide revisar valores faltantes en `users`, pero MovieLens 32M no trae un archivo de usuarios.
- **Decisión:** `ingest` escribe `users.parquet` (userId, n_ratings, primer y último timestamp) a partir de `ratings`.
  Se validan sus columnas y se usa para comprobar que los usuarios de `tags` existen.
- **Cómo revertir:** si llega un `users.csv` real, se agrega a `RAW_FILES` y reemplaza a la tabla derivada.

### D-10 · `serving.min_ratings = 50`, separado del umbral de limpieza

- **Contexto:** el checklist de US1.3 t2 separa `data.min_ratings` (qué datos entran al entrenamiento) de
  `serving.min_ratings` (qué películas se muestran o recomiendan).
- **Decisión:** `serving.min_ratings` solo afecta los rankings del dashboard («mejor valoradas») y las películas
  similares del explorador. No cambia los datos limpios ni dispara etapas de DVC.
- **Estado:** valor inicial propuesto; **requiere validación del PO**.

### D-11 · Similitud entre películas: coseno sobre «le gustó» (nota ≥ 4)

- **Contexto:** US1.5 pide mapear películas, usuarios y sus reacciones, y ver grupos de gustos.
- **Decisión:** dos películas son similares cuando les gustan a las mismas personas:
  `sim(i, j) = |A_i ∩ A_j| / sqrt(|A_i|·|A_j|)`, con `A_x` = usuarios que le dieron ≥ 4 a `x`. Es la base de un
  recomendador item-item. El grafo dibuja las k vecinas más fuertes de cada película. Usa vis-network 9.1.9,
  copiado en `app/static/` (licencia Apache-2.0/MIT) para no depender de un CDN.
- **Evidencia:** grafo de 250 películas en ~1,5 s; las vecinas de *The Matrix* son *Fight Club*, *El Señor de los
  Anillos* y *Star Wars V*.
