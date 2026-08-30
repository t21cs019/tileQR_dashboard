"""tileQR_data から最新データを取得して統合テーブルを作り直す。

主データ源 tileQR_data の derived/*.parquet と machines.yaml を HTTPS で取得し、
inbox（補助）と合わせて store/runs.parquet を再構築する。

実行: PYTHONPATH=src python -m tileqr_dashboard.sync_data
用途: コンテナ起動時の初期取得、cron 等での定期更新、手動更新。
"""
from __future__ import annotations

from . import datarepo


def main() -> None:
    datarepo.sync()


if __name__ == "__main__":
    main()
