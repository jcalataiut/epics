# Épica 1 — comandos del equipo. `make help` lista todo.
#
#   make dashboard   ← UN COMANDO: entorno + pipeline + dashboard
#
SHELL := /bin/bash
# En discos de red lentos se puede crear el entorno en disco local:
#   make dashboard VENV=/tmp/epic1-venv
VENV  ?= .venv
BIN   := $(abspath $(VENV))/bin
export PATH := $(BIN):$(HOME)/.local/bin:$(PATH)
PORT  ?= 8501

# Servidor compartido con `ulimit -v` (16 GB para @ialab): limitar hilos evita que
# OpenBLAS/DuckDB reserven gigas de memoria virtual (ver D-07).
export OPENBLAS_NUM_THREADS ?= 4
export OMP_NUM_THREADS ?= 4
export EPIC1_DUCKDB_THREADS ?= 8
export EPIC1_DUCKDB_MEMORY ?= 4GB

.PHONY: help setup pipeline clean-data test eda eda-check dashboard metrics status

help:  ## Muestra esta ayuda
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*## "}{printf "  make %-11s %s\n",$$1,$$2}'

setup: $(VENV)/.installed  ## Crea .venv e instala dependencias fijadas (requirements.txt)

$(VENV)/.installed: requirements.txt pyproject.toml
	@if command -v uv >/dev/null 2>&1; then \
	   uv venv $(VENV) --python 3.12 -q --allow-existing && \
	   uv pip install -q --python $(BIN)/python -r requirements.txt -e . ; \
	 else \
	   python3 -m venv $(VENV) && $(BIN)/pip install -q -r requirements.txt -e . ; \
	 fi
	@[ -d .git ] || git init -q   # DVC necesita git (p. ej. al descomprimir el .zip)
	@touch $@

pipeline: setup  ## Ejecuta el pipeline DVC (se detiene si falla un check bloqueante)
	dvc repro

clean-data: setup  ## US1.3 t2: controles + limpieza por umbral (data.min_ratings) e informe corto
	dvc repro clean
	@echo "Informe: reports/clean_report.md · Métricas: dvc metrics show"

test: setup  ## Tests unitarios y de integración (checks, k-core, gate, EDA)
	pytest

eda: setup  ## Ejecuta el notebook de EDA y guarda gráficos y tablas en el mismo archivo
	jupyter execute --inplace notebooks/01_eda_ratings.ipynb

eda-check: setup  ## Ejecuta el notebook de EDA de punta a punta (sin guardar salidas)
	python -c "import nbformat, nbclient; nb = nbformat.read('notebooks/01_eda_ratings.ipynb', 4); nbclient.NotebookClient(nb, timeout=600, resources={'metadata': {'path': 'notebooks'}}).execute(); print('EDA OK')"

dashboard: setup  ## UN COMANDO: actualiza datos (dvc repro) y abre el dashboard (puerto 8501, o PORT=…)
	@if python -c "from movielens.config import load_params as p, resolve as r; import sys; sys.exit(not (r(p()['data']['raw_dir']) / 'ratings.csv').exists())"; then \
	   dvc repro || echo -e "\nPipeline detenido por un control bloqueante: el dashboard lo muestra en 'Calidad de datos'.\n"; \
	 else echo -e "\nNo está el dataset crudo (data.raw_dir): se usan los datos procesados de data/.\n"; fi
	@# En VS Code (también Remote-SSH) $$BROWSER abre la URL en tu navegador y reenvía el puerto solo.
	@if [ -n "$$BROWSER" ]; then ( for i in $$(seq 120); do \
	   curl -sf -o /dev/null http://localhost:$(PORT)/_stcore/health && exec "$$BROWSER" http://localhost:$(PORT); \
	   sleep 1; done ) & fi
	streamlit run app/dashboard.py --server.port $(PORT) --server.headless true

metrics: setup  ## Métricas de calidad y limpieza versionadas (dvc metrics show)
	dvc metrics show

status: setup  ## ¿Datos al día con código y params? (dvc status)
	dvc status
