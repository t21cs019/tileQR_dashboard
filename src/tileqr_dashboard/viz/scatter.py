"""コアあたりキャッシュ量 × 最適 nb の散布図。

threads・size を固定し、その組み合わせの CPU(label) ごとに1点をプロットする。
メタJSON または cpus.toml プリセットで CPU キャッシュ情報が分かる label だけが対象。
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
        cache_mb = metrics.cache_per_core_mb(g.iloc[0])
        if cache_mb is None:
            continue
        agg = metrics.aggregate_runs(df, label, threads, size)
        if agg.empty:
            continue
        best = metrics.best_row(agg)
        rows.append({
            "label": label,
            "cache_per_core_mb": cache_mb,
            "best_nb": int(best["nb"]),
            "best_gflops": float(best["GFlops"]),
        })

    if not rows:
        print(
            f"  [skip] threads={threads}, size={size}: CPUキャッシュ情報を持つ "
            "label がありません。メタJSON(l2_per_core_kb / l3_total_mb / sockets / "
            "cores_per_socket) または cpus.toml プリセットが必要です。"
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

    ax.scatter(pts["cache_per_core_mb"], pts["best_nb"], s=90, label="実測")
    for _, r in pts.iterrows():
        ax.annotate(r["label"], (r["cache_per_core_mb"], r["best_nb"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=9)

    ax.set_xlabel("コアあたりキャッシュ量 (MB)")
    ax.set_ylabel("最適 nb（GFlops最大）")
    ax.set_title(f"コアあたりキャッシュ量 × 最適タイルサイズ nb（threads={threads}, size={size}）")
    ax.legend()
    ax.grid(True, alpha=0.3)
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
