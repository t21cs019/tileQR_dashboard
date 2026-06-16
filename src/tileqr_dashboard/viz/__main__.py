"""可視化の入口（サブコマンド方式）。

実行例:
  PYTHONPATH=src python -m tileqr_dashboard.viz heatmap --host par001 --threads 128
  PYTHONPATH=src python -m tileqr_dashboard.viz heatmap --all
  PYTHONPATH=src python -m tileqr_dashboard.viz scatter
  PYTHONPATH=src python -m tileqr_dashboard.viz compare
  PYTHONPATH=src python -m tileqr_dashboard.viz all
"""
from __future__ import annotations

import argparse

from ..ingest import load_store
from . import compare, heatmap, line, scatter


def main() -> None:
    parser = argparse.ArgumentParser(description="tileQR ダッシュボード可視化")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_hm = sub.add_parser("heatmap", help="nb×ib ヒートマップ")
    p_hm.add_argument("--host", help="対象ホスト（例 par001）")
    p_hm.add_argument("--threads", type=int, help="対象スレッド数")
    p_hm.add_argument("--all", action="store_true", help="全 host×threads を生成")

    p_ln = sub.add_parser("line", help="nb×GFlops 折れ線（CPU比較）")
    p_ln.add_argument("--threads", type=int, help="対象スレッド数（省略時は全部）")

    sub.add_parser("scatter", help="キャッシュ量×最適nb 散布図")
    sub.add_parser("compare", help="CPU比較表")
    sub.add_parser("all", help="全部生成")

    args = parser.parse_args()
    df = load_store()

    if args.cmd == "heatmap":
        if args.all or not (args.host and args.threads):
            if not args.all:
                print("[info] --host/--threads 未指定のため --all として実行します")
            heatmap.make_all(df)
        else:
            heatmap.make_heatmap(df, args.host, args.threads)
    elif args.cmd == "line":
        if args.threads:
            line.make_line(df, args.threads)
        else:
            line.make_all(df)
    elif args.cmd == "scatter":
        scatter.make_scatter(df)
    elif args.cmd == "compare":
        compare.make_compare(df)
    elif args.cmd == "all":
        print("[viz] heatmap (全組み合わせ)")
        heatmap.make_all(df)
        print("[viz] line (CPU比較)")
        line.make_all(df)
        print("[viz] scatter")
        scatter.make_scatter(df)
        print("[viz] compare")
        compare.make_compare(df)


if __name__ == "__main__":
    main()
