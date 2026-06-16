"""nb × スレッドあたりキャッシュ量 の散布図（cache_vs_tile_v3.py のスタイル）。

threads・size を固定し、その組み合わせの CPU(label) ごとに1点をプロットする。
メタJSON または cpus.toml プリセットでキャッシュ情報が分かる label だけが対象。

横軸 = nb（最適タイルサイズ）、縦軸 = スレッドあたりキャッシュ量(KB)。
理論帯 nb ≈ sqrt(cache×ratio / 32) の 25〜75% 帯と 50% ラインを重ねる。
（32 = 8 byte(double) × 4）
label に "AOBA" を含むものは別色（オレンジ）・別マーカー（◇）で強調する。
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .. import metrics, paths  # noqa: E402
from .fonts import setup_japanese_font  # noqa: E402

_AOBA_COLOR = "#e07b00"
_OTHER_COLOR = "steelblue"


def make_scatter(
    df: pd.DataFrame,
    threads: int,
    size: int,
    out_png: Path | None = None,
) -> Path | None:
    setup_japanese_font()

    sub = df[(df["threads"] == threads) & (df["size"] == size)]
    if sub.empty:
        print(f"  [skip] threads={threads}, size={size} のデータなし")
        return None

    rows = []
    for label, g in sub.groupby("label"):
        cache_kb = metrics.cache_per_thread_kb(g.iloc[0])
        if cache_kb is None:
            continue
        agg = metrics.aggregate_runs(df, label, threads, size)
        if agg.empty:
            continue
        best = metrics.best_row(agg)
        rows.append({
            "label": label,
            "cache_kb": cache_kb,
            "best_nb": int(best["nb"]),
            "best_gflops": float(best["GFlops"]),
        })

    if not rows:
        print(
            f"  [skip] threads={threads}, size={size}: キャッシュ情報を持つ "
            "label がありません。メタJSON(l2_per_core_kb / l3_per_socket_mb / sockets / "
            "cores_per_socket) または cpus.toml プリセットが必要です。"
        )
        return None

    pts = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(12, 9))

    cache_range = np.linspace(pts["cache_kb"].min() * 0.7, pts["cache_kb"].max() * 1.3, 200)
    nb_25 = np.array([metrics.theory_nb_from_cache_kb(c, 0.25) for c in cache_range])
    nb_50 = np.array([metrics.theory_nb_from_cache_kb(c, 0.50) for c in cache_range])
    nb_75 = np.array([metrics.theory_nb_from_cache_kb(c, 0.75) for c in cache_range])

    # グレー塗りつぶし（25%〜75%）
    ax.fill_betweenx(cache_range, nb_25, nb_75, alpha=0.22, color="gray")
    # 50%ライン（赤）
    ax.plot(nb_50, cache_range, color="red", linewidth=2.0, zorder=4)

    for _, r in pts.iterrows():
        is_aoba = "AOBA" in r["label"]
        color = _AOBA_COLOR if is_aoba else _OTHER_COLOR
        marker = "D" if is_aoba else "o"
        ax.scatter(r["best_nb"], r["cache_kb"], s=170, color=color, marker=marker, zorder=5)
        ax.annotate(
            r["label"], (r["best_nb"], r["cache_kb"]),
            textcoords="offset points", xytext=(8, 8),
            fontsize=10, fontweight="bold", color=color, va="center",
        )

    ax.set_xlabel("Tile Size (nb)", fontsize=13)
    ax.set_ylabel("Cache Size / Thread (KB)", fontsize=13)
    ax.set_title(
        f"CPU Cache Size vs Tile Size（threads={threads}, size={size}）",
        fontsize=15, fontweight="bold",
    )
    ax.grid(True, linestyle="-", alpha=0.4, color="gray")
    ax.set_axisbelow(True)

    grey_patch = mpatches.Patch(color="gray", alpha=0.3, label="理論帯 (25〜75% 使用)")
    red_line = plt.Line2D([0], [0], color="red", linewidth=2, label="50% 使用ライン")
    blue_dot = plt.Line2D(
        [0], [0], marker="o", color="w", markerfacecolor=_OTHER_COLOR,
        markersize=9, label="その他 CPU(label)",
    )
    orange_dot = plt.Line2D(
        [0], [0], marker="D", color="w", markerfacecolor=_AOBA_COLOR,
        markersize=9, label="AOBA",
    )
    ax.legend(handles=[grey_patch, red_line, blue_dot, orange_dot],
              loc="upper left", fontsize=10, framealpha=0.9)

    fig.tight_layout()

    if out_png is None:
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png = paths.OUTPUT_DIR / f"scatter_cache_vs_nb_t{threads}_s{size}.png"
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f"  [ok] {out_png.name}  ({len(pts)} 点)")
    return out_png


def make_all(df: pd.DataFrame) -> list[Path]:
    """全 (threads, size) の組み合わせで散布図を作る。"""
    outs = []
    combos = df[["threads", "size"]].drop_duplicates().sort_values(["threads", "size"])
    for _, row in combos.iterrows():
        out = make_scatter(df, int(row["threads"]), int(row["size"]))
        if out:
            outs.append(out)
    return outs
