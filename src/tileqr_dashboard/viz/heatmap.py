"""nb × ib の GFlops ヒートマップを生成する。

store(統合テーブル) から host・threads でフィルタして描画する。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from .. import paths  # noqa: E402


def make_heatmap(
    df: pd.DataFrame,
    host: str,
    threads: int,
    out_png: Path | None = None,
) -> Path | None:
    sub = df[(df["host"] == host) & (df["threads"] == threads)]
    if sub.empty:
        print(f"  [skip] host={host}, threads={threads} のデータなし")
        return None

    pivot = sub.pivot_table(index="ib", columns="nb", values="GFlops", aggfunc="mean")
    pivot = pivot.iloc[::-1]  # ib が大きい方を上に

    max_val = pivot.max().max()
    max_ib, max_nb = pivot.stack().idxmax()

    label = sub["label"].iloc[0]

    plt.figure(figsize=(12, 8))
    sns.heatmap(pivot, annot=False, cmap="YlGnBu", cbar_kws={"label": "GFlop/s"})
    plt.scatter(
        pivot.columns.get_loc(max_nb) + 0.5,
        pivot.index.get_loc(max_ib) + 0.5,
        color="red", s=120, zorder=5,
        label=f"Max {max_val:.1f} GFlop/s\n(nb={max_nb}, ib={max_ib})",
    )
    plt.legend(loc="upper left", bbox_to_anchor=(1.18, 1))
    plt.title(f"GFlop/s heatmap — {label} [{host}] (threads={threads})")
    plt.xlabel("nb (tile size)")
    plt.ylabel("ib (inner block size)")
    plt.tight_layout()

    if out_png is None:
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png = paths.OUTPUT_DIR / f"heatmap_{host}_t{threads}.png"
    plt.savefig(out_png, dpi=150)
    plt.close()
    print(f"  [ok] {out_png.name}  (max {max_val:.1f} @ nb={max_nb}, ib={max_ib})")
    return out_png


def make_all(df: pd.DataFrame) -> list[Path]:
    """全 host × threads の組み合わせでヒートマップを作る。"""
    outs = []
    combos = df[["host", "threads"]].drop_duplicates().sort_values(["host", "threads"])
    for _, row in combos.iterrows():
        out = make_heatmap(df, row["host"], int(row["threads"]))
        if out:
            outs.append(out)
    return outs
