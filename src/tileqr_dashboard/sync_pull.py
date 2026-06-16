"""取り込みの入口。

  1. 各ソースをアダプタで pull（OneDriveはrclone、manualは確認のみ）
  2. inbox を走査して統合テーブル(store/runs.parquet)を再構築

実行: PYTHONPATH=src python -m tileqr_dashboard.sync_pull
"""
from __future__ import annotations

import argparse

from . import adapters, ingest
from .config import load_sources


def main() -> None:
    parser = argparse.ArgumentParser(description="ベンチマーク結果の取り込み")
    parser.add_argument(
        "--only", nargs="*", default=None,
        help="指定したソースキーだけ pull する（省略時は全部）",
    )
    parser.add_argument(
        "--no-pull", action="store_true",
        help="アダプタpullをスキップし、inboxの再走査だけ行う",
    )
    args = parser.parse_args()

    sources = load_sources()

    if not args.no_pull:
        targets = sources
        if args.only:
            targets = {k: v for k, v in sources.items() if k in args.only}
            unknown = set(args.only) - set(sources)
            if unknown:
                print(f"[warn] 未知のソース: {sorted(unknown)}")
        print(f"[sync] {len(targets)} ソースを取得します")
        for source in targets.values():
            adapters.pull(source)

    print("[sync] inbox を走査して統合テーブルを再構築します")
    ingest.build_store(sources)


if __name__ == "__main__":
    main()
