#!/bin/bash
# cron_atualizar.sh — Executado diariamente pelo cron para recarregar o XLSX.
#
# Adicione ao crontab do usuário:
#   0 6 * * 1-5 /home/daianasales/vscode/datapipeline/dashboard_cggac/deploy/cron_atualizar.sh >> /var/log/dashboard_cggac/cron.log 2>&1
#
# O XLSX deve estar atualizado em CGGAC_XLSX_PATH (configurado no .env).

set -e

PROJECT_DIR="/home/daianasales/vscode/datapipeline/dashboard_cggac"
VENV_PYTHON="/home/daianasales/vscode/datapipeline/.venv/bin/python"
LOG_DIR="/var/log/dashboard_cggac"

mkdir -p "$LOG_DIR"

echo "========================================"
echo "Início da carga: $(date '+%Y-%m-%d %H:%M:%S')"

cd "$PROJECT_DIR"

# Carrega variáveis do .env sem necessidade de export manual
set -a
# shellcheck disable=SC1091
source "$PROJECT_DIR/.env" 2>/dev/null || true
set +a

"$VENV_PYTHON" manage.py carregar_xlsx

echo "Fim da carga: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
