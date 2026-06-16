"""CPU/ベンチマーク比較表をスライド向け(16:9)の画像として出力する。

(label, threads, size) ごとに1行。ピーク GFlops と最適 (nb, ib)、
（メタ/プリセットがあれば）CPU 名、集約に使った host 数をまとめる。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from .. import metrics, paths  # noqa: E402
from .fonts import setup_japanese_font  # noqa: E402

_COLUMNS = [
    "ラベル", "CPU", "スレッド", "サイズ",
    "ホスト数", "ピーク GFlop/s", "最適 nb", "最適 ib",
]


def _na(v) -> str:
    return "—" if (v is None or pd.isna(v)) else str(v)


def _build_rows(df: pd.DataFrame) -> list[list[str]]:
    rows = []
    combos = df[["label", "threads", "size"]].drop_duplicates()
    for _, combo in combos.iterrows():
        label, threads, size = combo["label"], int(combo["threads"]), int(combo["size"])
        agg = metrics.aggregate_runs(df, label, threads, size)
        if agg.empty:
            continue
        best = agg.loc[agg["GFlops"].idxmax()]
        sub = df[(df["label"] == label) & (df["threads"] == threads) & (df["size"] == size)]
        rows.append([
            label,
            _na(sub["cpu_model"].iloc[0]),
            str(threads),
            str(size),
            str(int(sub["host"].nunique())),
            f"{best['GFlops']:.1f}",
            str(int(best["nb"])),
            str(int(best["ib"])),
        ])
    # ラベル→スレッド→サイズ の順でソート
    rows.sort(key=lambda r: (r[0], int(r[2]), int(r[3])))
    return rows


def make_compare(df: pd.DataFrame, out_png: Path | None = None) -> Path | None:
    if df.empty:
        print("  [skip] データが空です")
        return None

    setup_japanese_font()
    rows = _build_rows(df)

    fig, ax = plt.subplots(figsize=(12.8, 7.2))  # 16:9
    ax.axis("off")
    ax.set_title("CPU別 tileQR ベンチマーク比較（dgeqrf）",
                 fontsize=16, pad=20)

    table = ax.table(cellText=rows, colLabels=_COLUMNS,
                     cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 1.8)

    # ヘッダ行の装飾
    for j in range(len(_COLUMNS)):
        cell = table[0, j]
        cell.set_facecolor("#2F5496")
        cell.set_text_props(color="white", fontweight="bold")
    # 行の縞模様
    for i in range(1, len(rows) + 1):
        for j in range(len(_COLUMNS)):
            if i % 2 == 0:
                table[i, j].set_facecolor("#F2F5FB")

    fig.tight_layout()

    if out_png is None:
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png = paths.OUTPUT_DIR / "compare_table.png"
    fig.savefig(out_png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [ok] {out_png.name}  ({len(rows)} 行)")
    return out_png
