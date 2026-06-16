"""可視化系で共有する計算ヘルパ。"""
from __future__ import annotations

import math

import pandas as pd


def cache_per_core_mb(row: pd.Series) -> float | None:
    """L2(per core) + L3(均等割り) をコアあたり MB で返す。欠損なら None。"""
    l2 = row.get("l2_per_core_kb")
    l3 = row.get("l3_total_mb")
    sockets = row.get("sockets")
    cps = row.get("cores_per_socket")
    if any(pd.isna(v) for v in (l2, l3, sockets, cps)):
        return None
    total_cores = sockets * cps
    if total_cores <= 0:
        return None
    return l2 / 1024.0 + l3 / total_cores


def theory_nb(cache_mb: float) -> float:
    """理論式 nb ≈ sqrt(CacheSize / 32)。32 = 8byte(double) × 4。"""
    return math.sqrt(cache_mb * 1024 * 1024 / 32.0)


def best_row(g: pd.DataFrame) -> pd.Series:
    """GFlops が最大の行を返す。"""
    return g.loc[g["GFlops"].idxmax()]


def heatmap_pivot(sub: pd.DataFrame) -> pd.DataFrame:
    """nb(列) × ib(行) の GFlops ピボットを返す。"""
    return sub.pivot_table(index="ib", columns="nb", values="GFlops", aggfunc="mean")
