#!/usr/bin/env bash
# コンテナ起動時の前処理 — ZimaOS 等で名前付きボリュームを使う運用向け。
#
#  1. config ボリュームが空なら、イメージ同梱の既定設定(config.default)を seed する。
#     （sources.toml / cpus.toml をボリューム経由で編集できるようにするため）
#  2. データ用ディレクトリを用意する（inbox/manual・onedrive, store, output, plan）。
#
# dashboard / receiver どちらのサービスでも共通で先に走る（compose の command を exec）。
set -euo pipefail

if [ -d /app/config.default ] && [ -z "$(ls -A /app/config 2>/dev/null || true)" ]; then
    echo "[entrypoint] config が空なので既定設定を seed します"
    cp -a /app/config.default/. /app/config/
fi

mkdir -p /app/inbox/manual /app/inbox/onedrive /app/store /app/output /app/plan /app/data_repo

# 起動時に tileQR_data を取得して統合テーブルを作る（TILEQR_SYNC_ON_START=1 のサービスのみ）。
# compose では dashboard サービスにだけ設定して二重取得を避ける。失敗しても起動は続行。
if [ "${TILEQR_SYNC_ON_START:-0}" = "1" ]; then
    echo "[entrypoint] 起動時に tileQR_data を取得します"
    uv run python -m tileqr_dashboard.sync_data || \
        echo "[entrypoint] tileQR_data 取得に失敗（起動は継続。UIの更新ボタンで再試行可）"
fi

exec "$@"
