# Publicar el dashboard en Streamlit Community Cloud

Guía para dejar el dashboard en una URL `https://<nombre>.streamlit.app` desplegada desde GitHub.
Se probó una simulación del despliegue: copia limpia sin datos, solo con `app/requirements.txt`, datos descargados
desde una URL y DuckDB limitado a 1 GB. Las 7 páginas cargaron sin errores con un máximo de 1,55 GB de memoria; el
límite de Community Cloud es de ~2,7 GB.

## Qué se sube y qué no

| Va al repositorio de GitHub | No va al repositorio |
|---|---|
| Todo el contenido de `Epic_1/`: `app/`, `src/`, `.streamlit/config.toml`, `params.yaml`, `dvc.yaml`, `dvc.lock`, `reports/`, `docs/`, `tests/`, `notebooks/`, `requirements.txt`, `pyproject.toml`, `Makefile`, `run_local.py` | `data/interim/` y `data/processed/` (los Parquet pesan ~340 MB y GitHub no acepta archivos de más de 100 MB) |
| `app/requirements.txt` (dependencias del dashboard en la nube) | `.streamlit/secrets.toml` (secretos: se cargan en la web de Streamlit) |
| | `.venv/`, `.dvc/cache/`, los `.zip` (ya están en `.gitignore`) |

Los datos se publican aparte, como un archivo `epic1_data.zip`, y el dashboard los descarga solo al arrancar
(`app/bootstrap.py`).

## Archivos que usa Community Cloud

| Archivo | Para qué |
|---|---|
| `app/dashboard.py` | **Punto de entrada** (*Main file path*) |
| `app/requirements.txt` | Dependencias. Community Cloud busca primero junto al punto de entrada, así que instala solo lo que usa el dashboard (sin DVC, Jupyter ni pytest) |
| `.streamlit/config.toml` | Tema y opciones. **Debe estar en la raíz del repositorio** |
| `app/bootstrap.py` | Hace importable `src/movielens`, lee los secretos `EPIC1_*` y descarga los datos si faltan |
| Secretos (en la web, no en git) | `EPIC1_DATA_URL`, y opcionalmente límites de DuckDB y un token |
| `epic1_data.zip` (fuera de git) | `data/interim` + `data/processed` + licencia de MovieLens (~350 MB) |

> **Importante:** la raíz del repositorio debe ser el contenido de `Epic_1/`, de modo que `.streamlit/` quede en la
> raíz. Si el repositorio del equipo tiene `Epic_1/` como subcarpeta, mueve o copia `Epic_1/.streamlit/` a la raíz
> del repositorio. El resto funciona igual, con *Main file path* = `Epic_1/app/dashboard.py`.

## Paso a paso

### 1. Crear el repositorio y subir el código

```bash
cd Epic_1
git init                       # si todavía no es un repositorio
git add .
git commit -m "Épica 1: pipeline de datos y dashboard"
git branch -M main
git remote add origin https://github.com/<organización>/<repositorio>.git
git push -u origin main
```

Antes del push, comprueba con `git status` que no aparezcan archivos `.parquet` ni `secrets.toml`.

### 2. Publicar los datos (`epic1_data.zip`)

El paquete se genera con:

```bash
cd Epic_1
cp ../ml-32m/README.txt data/MOVIELENS_README.txt     # licencia de MovieLens
zip -r ../epic1_data.zip data/interim data/processed data/MOVIELENS_README.txt
```

**Repositorio público (lo más simple):**

1. En GitHub, ve a **Releases → Draft a new release** y crea el tag `data-v1`.
2. Adjunta `epic1_data.zip` (los releases aceptan archivos de hasta 2 GB) y publica.
3. Copia el enlace del asset. Su forma es:
   `https://github.com/<organización>/<repositorio>/releases/download/data-v1/epic1_data.zip`

**Repositorio privado:** el enlace anterior pide autenticación.

1. Crea un *fine-grained token* de GitHub con permiso de solo lectura de *Contents* sobre ese repositorio.
2. Usa como URL la del asset en la API: `https://api.github.com/repos/<org>/<repo>/releases/assets/<id>`.
   El `<id>` aparece en `gh api repos/<org>/<repo>/releases/tags/data-v1`.
3. Agrega el token como secreto `EPIC1_DATA_TOKEN`.

También sirve cualquier URL directa de descarga, por ejemplo un dataset de Hugging Face o un bucket.

Licencia: MovieLens permite redistribuir el dataset y sus transformaciones bajo las mismas condiciones y prohíbe el
uso comercial sin permiso de GroupLens. El paquete incluye su `README.txt` con la licencia.

### 3. Crear la app en Community Cloud

1. Entra a <https://share.streamlit.io> con tu cuenta de GitHub.
2. Para un repositorio privado: **Settings → Linked accounts → Source control → Connect here → Authorize streamlit**.
   Necesitas permisos de administrador del repositorio. Si es de una organización, la organización debe dar acceso.
3. **Create app → Deploy a public app from GitHub** y completa:
   - **Repository:** `<organización>/<repositorio>`
   - **Branch:** `main`
   - **Main file path:** `app/dashboard.py`
   - **App URL:** el subdominio que prefieras, p. ej. `movielens-epica1`
4. **Advanced settings:**
   - **Python version:** 3.12
   - **Secrets:**

     ```toml
     EPIC1_DATA_URL = "https://github.com/<organización>/<repositorio>/releases/download/data-v1/epic1_data.zip"
     EPIC1_DUCKDB_MEMORY = "1GB"      # deja margen bajo el límite de ~2,7 GB de la app
     EPIC1_DUCKDB_THREADS = "2"       # Community Cloud da como máximo 2 núcleos
     # EPIC1_DATA_TOKEN = "github_pat_…"   # solo si el repositorio es privado
     ```

5. Haz clic en **Deploy**. El primer arranque instala dependencias y descarga los datos (unos minutos). Después,
   cada página tarda pocos segundos.

### 4. Compartir

- **App de un repositorio público:** es pública.
- **App de un repositorio privado:** es privada. Invita a tus compañeros por correo con **Share** o en
  **App settings → Sharing → Only specific people can view this app**.
- **Límite:** Community Cloud permite **una sola app privada** por cuenta.
- **Inactividad:** sin visitas durante 12 horas, la app se duerme y cualquiera con acceso la despierta con un botón.
  Al despertar vuelve a descargar los datos.

## Actualizar

- **Código:** cada `git push` a la rama configurada redespliega la app sola.
- **Datos:** si cambia el pipeline (por ejemplo, `data.min_ratings`), corre `make pipeline` localmente, vuelve a
  generar `epic1_data.zip` y súbelo como un release nuevo (`data-v2`). Luego actualiza `EPIC1_DATA_URL` en
  **App settings → Secrets** y haz **Reboot app**. Haz commit de `dvc.lock` y `reports/` en el mismo cambio, para que
  la página de calidad y el informe de limpieza coincidan con los datos.

## Diferencias con la versión local

- El botón **Ejecutar dvc status** de la página *Pipeline* no funciona en la nube, porque DVC no se instala. La
  página lo indica y el resto se ve igual.
- El pipeline no corre en la nube. El dashboard muestra los datos y reportes que publicaste.

## Si algo falla

| Síntoma en Community Cloud | Causa y solución |
|---|---|
| `ModuleNotFoundError: movielens` | El *Main file path* no es `app/dashboard.py` o falta `app/bootstrap.py` |
| «No hay datos procesados» | Falta el secreto `EPIC1_DATA_URL` o la URL no es una descarga directa del `.zip` |
| Error HTTP 404 al descargar | Repositorio privado: usa la URL de la API y `EPIC1_DATA_TOKEN` |
| «This app has gone over its resource limits» | Baja `EPIC1_DUCKDB_MEMORY` a `768MB` y haz **Reboot app** |
| El tema se ve distinto al local | `.streamlit/config.toml` no está en la raíz del repositorio |
