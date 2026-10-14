#!/bin/bash
# Sobe a instancia de verificacao A na porta 8081 (banco e arquivos em backend/dados/verif).
cd "/c/Users/<usuario>/Nova Dashboard Lotufo/backend" || exit 1
export DASH_DEV=1 DASH_SEM_JOBS=1 DASH_SEM_FRONTEND=1
export DASH_DB_PATH="$(pwd)/dados/verif/dashboard.db"
export DASH_GRAPH_SIMULADOR="$(pwd)/dados/verif/correio-simulado"
exec .venv/Scripts/python.exe -m uvicorn --factory app.main:create_app --port 8081 >> dados/verif/uvicorn-8081.log 2>&1
