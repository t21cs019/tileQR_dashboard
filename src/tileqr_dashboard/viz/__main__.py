"""可視化の入口（サブコマンド方式）。

識別単位は host ではなく CPU(label) / threads / size（v0.4.0〜）。

実行例:
  PYTHONPATH=src python -m tileqr_dashboard.viz heatmap --label AOBA-B --threads 64 --size 8192
  PYTHONPATH=src python -m tileqr_dashboard.viz heatmap --all
  PYTHONPATH=src python -m tileqr_dashboard.viz line --threads 64 --size 8192
  PYTHONPATH=src python -m tileqr_dashboard.viz scatter --threads 64 --size 8192
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
    p_hm.add_argument("--label", help="対象CPU(label)（例 AOBA-B）")
    p_hm.add_argument("--threads", type=int, help="対象スレッド数")
    p_hm.add_argument("--size", type=int, help="対象size")
    p_hm.add_argument("--all", action="store_true", help="全 label×threads×size を生成")

    p_ln = sub.add_parser("line", help="nb×GFlops 折れ線（CPU比較）")
    p_ln.add_argument("--threads", type=int, help="対象スレッド数（省略時は全部）")
    p_ln.add_argument("--size", type=int, help="対象size（省略時は全部）")

    p_sc = sub.add_parser("scatter", help="キャッシュ量×最適nb 散布図")
    p_sc.add_argument("--threads", type=int, help="対象スレッド数（省略時は全部）")
    p_sc.add_argument("--size", type=int, help="対象size（省略時は全部）")

    sub.add_parser("compare", help="CPU比較表")
    sub.add_parser("all", help="全部生成")

    args = parser.parse_args()
    df = load_store()

    if args.cmd == "heatmap":
        if args.all or not (args.label and args.threads and args.size):
            if not args.all:
                print("[info] --label/--threads/--size 未指定のため --all として実行します")
            heatmap.make_all(df)
        else:
            heatmap.make_heatmap(df, args.label, args.threads, args.size)
    elif args.cmd == "line":
        if args.threads and args.size:
            line.make_line(df, args.threads, args.size)
        else:
            line.make_all(df)
    elif args.cmd == "scatter":
        if args.threads and args.size:
            scatter.make_scatter(df, args.threads, args.size)
        else:
            scatter.make_all(df)
    elif args.cmd == "compare":
        compare.make_compare(df)
    elif args.cmd == "all":
        print("[viz] heatmap (全組み合わせ)")
        heatmap.make_all(df)
        print("[viz] line (CPU比較)")
        line.make_all(df)
        print("[viz] scatter")
        scatter.make_all(df)
        print("[viz] compare")
        compare.make_compare(df)


if __name__ == "__main__":
    main()
