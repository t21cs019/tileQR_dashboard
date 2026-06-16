"""nb × GFlops 折れ線グラフ（各nbで最適ibを選択、label別の系列）。

CPU(label)ごとに「nb を振ったときの到達 GFlops」を重ねて比較する。
各 nb では ib を振った中で最大の GFlops を採用する（最適ib選択）。
threads・size を固定し、同じ label の複数 host／試行は (nb, ib) ごとに
平均してから最適ib選択する（metrics.aggregate_runs）。
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
    size: int,
    out_png: Path | None = None,
) -> Path | None:
    sub = df[(df["threads"] == threads) & (df["size"] == size)]
    if sub.empty:
        print(f"  [skip] threads={threads}, size={size} のデータなし")
        return None

    setup_japanese_font()
    plt.figure(figsize=(12, 7))

    n_plotted = 0
    for label in sorted(sub["label"].dropna().unique()):
        agg = metrics.aggregate_runs(df, label, threads, size)
        if agg.empty:
            continue
        bb = metrics.best_per_nb(agg)
        (line,) = plt.plot(bb["nb"], bb["GFlops"], marker="o", markersize=3, label=label)

        best = metrics.best_row(bb)
        color = line.get_color()
        plt.scatter(
            [best["nb"]], [best["GFlops"]],
            marker="*", s=110, color=color, edgecolor="black", linewidth=0.5, zorder=5,
        )
        plt.annotate(
            f"Max {best['GFlops']:.1f} @ nb={int(best['nb'])}",
            (best["nb"], best["GFlops"]),
            textcoords="offset points", xytext=(6, 8), fontsize=8, color=color,
        )
        n_plotted += 1

    if n_plotted == 0:
        plt.close()
        print(f"  [skip] threads={threads}, size={size} のデータなし")
        return None

    plt.xlabel("nb (tile size)")
    plt.ylabel("GFlop/s")
    plt.title(f"nb × GFlops（threads={threads}, size={size}, 各nbで最適ib選択）")
    plt.legend(fontsize=9)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    if out_png is None:
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png = paths.OUTPUT_DIR / f"line_nb_gflops_t{threads}_s{size}.png"
    plt.savefig(out_png, dpi=150)
    plt.close()
    print(f"  [ok] {out_png.name}  ({n_plotted} CPU(label))")
    return out_png


def make_all(df: pd.DataFrame) -> list[Path]:
    """全 (threads, size) の組み合わせで折れ線を作る。"""
    outs = []
    combos = df[["threads", "size"]].drop_duplicates().sort_values(["threads", "size"])
    for _, row in combos.iterrows():
        out = make_line(df, int(row["threads"]), int(row["size"]))
        if out:
            outs.append(out)
    return outs
