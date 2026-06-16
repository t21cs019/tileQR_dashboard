"""コアあたりキャッシュ量 × 最適 nb の散布図。

メタJSON に CPU キャッシュ情報があるホストだけが対象。
理論曲線 nb ≈ sqrt(CacheSize / 32) を重ねて、実測の最適 nb と比較する。
（32 = 8 byte(double) × 4、実用域は理論値の 25〜75% とされる）
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .. import metrics, paths  # noqa: E402
from .fonts import setup_japanese_font  # noqa: E402


def make_scatter(df: pd.DataFrame, out_png: Path | None = None) -> Path | None:
    setup_japanese_font()

    rows = []
    for (host, threads), g in df.groupby(["host", "threads"]):
        cache_mb = metrics.cache_per_core_mb(g.iloc[0])
        if cache_mb is None:
            continue
        best = g.loc[g["GFlops"].idxmax()]
        rows.append({
            "host": host,
            "label": g["label"].iloc[0],
            "threads": int(threads),
            "cache_per_core_mb": cache_mb,
            "best_nb": int(best["nb"]),
            "best_gflops": float(best["GFlops"]),
        })

    if not rows:
        print(
            "  [skip] CPUキャッシュ情報を持つホストがありません。"
            "メタJSON(l2_per_core_kb / l3_total_mb / sockets / cores_per_socket)が必要です。"
        )
        return None

    pts = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(10, 7))

    # 理論曲線（実用域 25〜75% を帯で表示）
    xs = np.linspace(pts["cache_per_core_mb"].min() * 0.7,
                     pts["cache_per_core_mb"].max() * 1.3, 100)
    theory = np.array([metrics.theory_nb(x) for x in xs])
    ax.plot(xs, theory, "--", color="gray", label="理論値 nb≈√(cache/32)")
    ax.fill_between(xs, theory * 0.25, theory * 0.75, color="gray", alpha=0.12,
                    label="実用域 (25〜75%)")

    for threads, g in pts.groupby("threads"):
        ax.scatter(g["cache_per_core_mb"], g["best_nb"], s=90,
                   label=f"{threads} threads")
        for _, r in g.iterrows():
            ax.annotate(r["host"], (r["cache_per_core_mb"], r["best_nb"]),
                        textcoords="offset points", xytext=(6, 4), fontsize=9)

    ax.set_xlabel("コアあたりキャッシュ量 (MB)")
    ax.set_ylabel("最適 nb（GFlops最大）")
    ax.set_title("コアあたりキャッシュ量 × 最適タイルサイズ nb")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if out_png is None:
        paths.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_png = paths.OUTPUT_DIR / "scatter_cache_vs_nb.png"
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    print(f"  [ok] {out_png.name}  ({len(pts)} 点)")
    return out_png
