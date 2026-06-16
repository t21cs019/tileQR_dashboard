"""nb × GFlops 折れ線グラフ（各nbで最適ibを選択、host別の系列）。

CPU(host)ごとに「nb を振ったときの到達 GFlops」を重ねて比較する。
各 nb では ib を振った中で最大の GFlops を採用する（最適ib選択）。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .. import metrics, paths  # noqa: E402
from .fonts import setup_japanese_font  # noqa: E402


def make_line(
    df: pd.DataFrame,
    threads: int,
    out_png: Path | None = None,
) -> Path | None:
    sub = df[df["threads"] == threads]
    if sub.empty:
        print(f"  [skip] threads={threads} のデータなし")
        return None

    setup_japanese_font()
    plt.figure(figsize=(12, 7))

    for host, g in sub.groupby("host"):
        bb = metrics.best_per_nb(g)
        label = f"{g['label'].iloc[0]} [{host}]"
        plt.plot(bb["nb"], bb["GFlops"], marker="o", markersize=3, label=label)

    plt.xlabel("nb (tile size)")
    plt.ylabel("GFlop/s")
    plt.title(f"nb × GFlops（threads={threads}, 各nbで最適ib選択）")
    plt.legend(fontsize=9)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    if out_png is None:
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png = paths.OUTPUT_DIR / f"line_nb_gflops_t{threads}.png"
    plt.savefig(out_png, dpi=150)
    plt.close()
    print(f"  [ok] {out_png.name}  ({sub['host'].nunique()} ホスト)")
    return out_png


def make_all(df: pd.DataFrame) -> list[Path]:
    outs = []
    for threads in sorted(df["threads"].unique()):
        out = make_line(df, int(threads))
        if out:
            outs.append(out)
    return outs
