# Informe de limpieza

Ejecución: 2026-11-25T18:45:26+00:00 UTC · umbral `data.min_ratings` = 10

## 1. Controles de calidad (US1.3 t1)

37 de 37 controles pasan. Problemas encontrados por cada control:

| Control | Tabla | Severidad | Problemas | Resultado |
|---|---|---|---:|---|
| Existe ratings.csv | ratings | bloqueante | 0 | pasa |
| MD5 de ratings.csv coincide con checksums.txt | ratings | bloqueante | 0 | pasa |
| Existe movies.csv | movies | bloqueante | 0 | pasa |
| MD5 de movies.csv coincide con checksums.txt | movies | bloqueante | 0 | pasa |
| Existe tags.csv | tags | bloqueante | 0 | pasa |
| MD5 de tags.csv coincide con checksums.txt | tags | bloqueante | 0 | pasa |
| Existe links.csv | links | bloqueante | 0 | pasa |
| MD5 de links.csv coincide con checksums.txt | links | bloqueante | 0 | pasa |
| ratings.csv se parsea con el esquema esperado | ratings | bloqueante | 0 | pasa |
| movies.csv se parsea con el esquema esperado | movies | bloqueante | 0 | pasa |
| tags.csv se parsea con el esquema esperado | tags | bloqueante | 0 | pasa |
| links.csv se parsea con el esquema esperado | links | bloqueante | 0 | pasa |
| Esquema de ratings (columnas y tipos) | ratings | bloqueante | 0 | pasa |
| Esquema de movies (columnas y tipos) | movies | bloqueante | 0 | pasa |
| Esquema de users (columnas y tipos) | users | bloqueante | 0 | pasa |
| Sin valores faltantes en ratings.userId | ratings | bloqueante | 0 | pasa |
| Sin valores faltantes en ratings.movieId | ratings | bloqueante | 0 | pasa |
| Sin valores faltantes en ratings.rating | ratings | bloqueante | 0 | pasa |
| Sin valores faltantes en ratings.timestamp | ratings | bloqueante | 0 | pasa |
| Sin valores faltantes en movies.movieId | movies | bloqueante | 0 | pasa |
| Sin valores faltantes en movies.title | movies | bloqueante | 0 | pasa |
| Sin valores faltantes en movies.genres | movies | bloqueante | 0 | pasa |
| Sin valores faltantes en users.userId | users | bloqueante | 0 | pasa |
| Sin valores faltantes en users.n_ratings | users | bloqueante | 0 | pasa |
| Sin valores faltantes en users.first_timestamp | users | bloqueante | 0 | pasa |
| Sin valores faltantes en users.last_timestamp | users | bloqueante | 0 | pasa |
| Notas dentro de la escala [0.5, 5.0] | ratings | bloqueante | 0 | pasa |
| Notas en pasos de 0.5 | ratings | bloqueante | 0 | pasa |
| Sin ratings repetidos (userId, movieId) | ratings | bloqueante | 0 | pasa |
| movieId único en movies | movies | bloqueante | 0 | pasa |
| userId único en users | users | bloqueante | 0 | pasa |
| Películas de ratings existen en movies | ratings | bloqueante | 0 | pasa |
| Usuarios de ratings existen en users | ratings | bloqueante | 0 | pasa |
| Películas de tags existen en movies | tags | bloqueante | 0 | pasa |
| Usuarios de tags existen en users | tags | bloqueante | 0 | pasa |
| Películas de links existen en movies | links | bloqueante | 0 | pasa |
| Fechas de rating plausibles | ratings | aviso | 0 | pasa |

## 2. Filtro por umbral (US1.3 t2): usuarios y películas con ≥ 10 ratings

| | Antes | Después | Eliminados | % eliminado |
|---|---:|---:|---:|---:|
| Ratings | 32.000.204 | 31.842.696 | 157.508 | 0,49% |
| Usuarios | 200.948 | 200.947 | 1 | 0,00% |
| Películas | 84.432 | 31.961 | 52.471 | 62,15% |

Densidad de la matriz: 0,1886% → 0,4958%. El filtro convergió en 3 iteraciones:

| Iteración | Ratings | Usuarios | Películas |
|---:|---:|---:|---:|
| 1 | 31.842.705 | 200.948 | 31.961 |
| 2 | 31.842.696 | 200.947 | 31.961 |
| 3 | 31.842.696 | 200.947 | 31.961 |

Datos limpios en `data/processed/` (versión en `dvc.lock`). Métricas: `dvc metrics show`.
