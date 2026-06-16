"""nb × ib の GFlops ヒートマップを生成する。

store(統合テーブル) から (label, threads, size) でフィルタ・集約して描画する。
同じ組み合わせの複数 host／試行は (nb, ib) ごとに平均する
（metrics.aggregate_runs）。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from .. import metrics, paths  # noqa: E402


def _slug(label: str) -> str:
    return str(label).replace(" ", "_")


def make_heatmap(
    df: pd.DataFrame,
    label: str,
    threads: int,
    size: int,
    out_png: Path | None = None,
) -> Path | None:
    agg = metrics.aggregate_runs(df, label, threads, size)
    if agg.empty:
        print(f"  [skip] label={label}, threads={threads}, size={size} のデータなし")
        return None

    pivot = agg.pivot_table(index="ib", columns="nb", values="GFlops", aggfunc="mean")
    pivot = pivot.iloc[::-1]  # ib が大きい方を上に

    max_val = pivot.max().max()
    max_ib, max_nb = pivot.stack().idxmax()

    plt.figure(figsize=(12, 8))
    sns.heatmap(pivot, annot=False, cmap="YlGnBu", cbar_kws={"label": "GFlop/s"})
    plt.scatter(
        pivot.columns.get_loc(max_nb) + 0.5,
        pivot.index.get_loc(max_ib) + 0.5,
        color="red", s=120, zorder=5,
        label=f"Max {max_val:.1f} GFlop/s\n(nb={max_nb}, ib={max_ib})",
    )
    plt.legend(loc="upper left", bbox_to_anchor=(1.18, 1))
    plt.title(f"GFlop/s heatmap — {label} (threads={threads}, size={size})")
    plt.xlabel("nb (tile size)")
    plt.ylabel("ib (inner block size)")
    plt.tight_layout()

    if out_png is None:
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png = paths.OUTPUT_DIR / f"heatmap_{_slug(label)}_t{threads}_s{size}.png"
    plt.savefig(out_png, dpi=150)
    plt.close()
    print(f"  [ok] {out_png.name}  (max {max_val:.1f} @ nb={max_nb}, ib={max_ib})")
    return out_png


def make_all(df: pd.DataFrame) -> list[Path]:
    """全 (label, threads, size) の組み合わせでヒートマップを作る。"""
    outs = []
    combos = (
        df[["label", "threads", "size"]]
        .drop_duplicates()
        .sort_values(["label", "threads", "size"])
    )
    for _, row in combos.iterrows():
        out = make_heatmap(df, row["label"], int(row["threads"]), int(row["size"]))
        if out:
            outs.append(out)
    return outs
