"""可視化系で共有する計算ヘルパ。"""
from __future__ import annotations

import math

import pandas as pd


def cache_per_thread_kb(row: pd.Series, threads: int) -> float | None:
    """使用ソケット数を考慮した、スレッドあたりキャッシュ量(KB)。欠損なら None。

    1ソケット分のキャッシュ(L2全コア + L3) に「実際に使うソケット数」を掛けて
    threads で割る。使用ソケット数は ceil(threads / cores_per_socket) を
    実装ソケット数で上限を切ったもの（例: 64スレッドなら1ソケットで足りる）。
    """
    l2 = row.get("l2_per_core_kb")
    l3 = row.get("l3_per_socket_mb")
    cps = row.get("cores_per_socket")
    sockets = row.get("sockets")
    if any(pd.isna(v) for v in (l2, l3, cps, sockets)):
        return None
    if pd.isna(threads) or threads <= 0 or cps <= 0:
        return None
    one_socket_kb = l2 * cps + l3 * 1024.0
    sockets_used = min(math.ceil(threads / cps), sockets)
    return one_socket_kb * sockets_used / threads


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
