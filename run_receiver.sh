#!/usr/bin/env bash
# 受信API を起動: http://localhost:8502
#   POST /upload/<key>  計測機からのCSV/メタ受信 → inbox → store再構築
#   GET/POST /plan/<key> 計測プラン(PROGRESS.md)の往復同期
# ローカル開発用。本番(ZimaOS)は docker compose の receiver サービスで起動する。
set -euo pipefail
cd "$(dirname "$0")"
PYTHONPATH=src uvicorn tileqr_dashboard.receiver:app \
    --host 0.0.0.0 --port 8502 "$@"
