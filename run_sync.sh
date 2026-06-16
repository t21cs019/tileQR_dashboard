#!/usr/bin/env bash
# 取り込み: アダプタpull → inbox走査 → store/runs.parquet 再構築
set -euo pipefail
cd "$(dirname "$0")"
PYTHONPATH=src python -m tileqr_dashboard.sync_pull "$@"
