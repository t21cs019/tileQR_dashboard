#!/usr/bin/env bash
# 可視化: heatmap / scatter / compare / all
set -euo pipefail
cd "$(dirname "$0")"
PYTHONPATH=src python -m tileqr_dashboard.viz "${@:-all}"
