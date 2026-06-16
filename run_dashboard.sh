#!/usr/bin/env bash
# Webダッシュボードを起動: http://localhost:8501
# LAN/Tailscaleに公開する場合は --server.address 0.0.0.0 を付ける
set -euo pipefail
cd "$(dirname "$0")"
PYTHONPATH=src streamlit run dashboard/app.py "$@"
