"""可視化系で共有する計算ヘルパ。"""
from __future__ import annotations

import math

import pandas as pd


def total_cache_kb(row: pd.Series) -> float | None:
    """総キャッシュ容量(KB) = L2(全コア合計) + L3(全ソケット合計)。欠損なら None。

    総キャッシュ = l2_per_core_kb × sockets × cores_per_socket
                 + l3_per_socket_mb × sockets × 1024
    """
    l2 = row.get("l2_per_core_kb")
    l3 = row.get("l3_per_socket_mb")
    sockets = row.get("sockets")
    cps = row.get("cores_per_socket")
    if any(pd.isna(v) for v in (l2, l3, sockets, cps)):
        return None
    return l2 * sockets * cps + l3 * sockets * 1024.0


def cache_per_thread_kb(row: pd.Series) -> float | None:
    """総キャッシュ(KB) ÷ threads。欠損なら None。"""
    total = total_cache_kb(row)
    threads = row.get("threads")
    if total is None or pd.isna(threads) or threads <= 0:
        return None
    return total / threads


def theory_nb_from_cache_kb(cache_kb: float, ratio: float = 1.0) -> float:
    """理論式 nb ≈ sqrt(cache_kb[KB] × 1024 × ratio / 32)。32 = 8byte(double) × 4。

    ratio はキャッシュ使用率（例: 0.25・0.5・0.75 で 25/50/75% 帯を描ける）。
    """
    return math.sqrt(cache_kb * 1024 * ratio / 32.0)


def best_row(g: pd.DataFrame) -> pd.Series:
    """GFlops が最大の行を返す。"""
    return g.loc[g["GFlops"].idxmax()]


def heatmap_pivot(sub: pd.DataFrame) -> pd.DataFrame:
    """nb(列) × ib(行) の GFlops ピボットを返す。"""
    return sub.pivot_table(index="ib", columns="nb", values="GFlops", aggfunc="mean")


def best_per_nb(g: pd.DataFrame) -> pd.DataFrame:
    """各 nb について GFlops 最大の行を選び、nb 昇順で返す（最適ib選択）。"""
    idx = g.groupby("nb")["GFlops"].idxmax()
    return g.loc[idx].sort_values("nb")


def aggregate_runs(
    df: pd.DataFrame,
    label: str,
    threads: int,
    size: int,
    hosts: list[str] | None = None,
) -> pd.DataFrame:
    """(label, threads, size) で絞り込み、(nb, ib) ごとに GFlops を平均する。

    複数 host／複数試行が同じ (nb, ib) を計測していても1点に集約される。
    hosts: 指定すると更にそのホスト集合に絞る（v0.5.0 のホスト内訳表示用、今は省略可）。
    """
    sub = df[
        (df["label"] == label) & (df["threads"] == threads) & (df["size"] == size)
    ]
    if hosts:
        sub = sub[sub["host"].isin(hosts)]
    return sub.groupby(["nb", "ib"], as_index=False)["GFlops"].mean()
