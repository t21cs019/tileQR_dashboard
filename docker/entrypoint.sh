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

mkdir -p /app/inbox/manual /app/inbox/onedrive /app/store /app/output /app/plan

exec "$@"
