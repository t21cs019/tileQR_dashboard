#!/usr/bin/env bash
# tileQR_data から最新データを取得して統合テーブルを作り直す。
#   取得元は既定 https://raw.githubusercontent.com/t21cs019/tileQR_data/main
#   別ブランチ/フォークは TILEQR_DATA_BASE で上書き可。
set -euo pipefail
cd "$(dirname "$0")"
PYTHONPATH=src python -m tileqr_dashboard.sync_data "$@"
