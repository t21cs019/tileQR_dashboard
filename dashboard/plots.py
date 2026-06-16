"""Plotly 図ビルダ（Streamlit から独立してテストできる純関数群）。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from tileqr_dashboard import metrics


def heatmap_fig(df: pd.DataFrame, host: str, threads: int) -> go.Figure | None:
    """nb × ib の GFlops ヒートマップ。ホバーで nb/ib/GFlops を表示。"""
    sub = df[(df["host"] == host) & (df["threads"] == threads)]
    if sub.empty:
        return None

    pivot = metrics.heatmap_pivot(sub)
    best = metrics.best_row(sub)
    label = sub["label"].iloc[0]

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns,
            y=pivot.index,
            colorscale="YlGnBu",
            colorbar=dict(title="GFlop/s"),
            hovertemplate="nb=%{x}<br>ib=%{y}<br>%{z:.1f} GFlop/s<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[int(best["nb"])],
            y=[int(best["ib"])],
            mode="markers",
            marker=dict(color="red", size=13, line=dict(color="white", width=1)),
            name="Max",
            hovertemplate=(
                f"Max {best['GFlops']:.1f} GFlop/s<br>"
                f"nb={int(best['nb'])}, ib={int(best['ib'])}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=f"{label} [{host}]  threads={threads}",
        xaxis_title="nb (tile size)",
        yaxis_title="ib (inner block size)",
        height=600,
        margin=dict(l=60, r=20, t=50, b=50),
    )
    return fig


def scatter_fig(df: pd.DataFrame) -> go.Figure | None:
    """コアあたりキャッシュ量 × 最適 nb。理論曲線と実用域を重ねる。"""
    rows = []
    for (host, threads), g in df.groupby(["host", "threads"]):
        cache_mb = metrics.cache_per_core_mb(g.iloc[0])
        if cache_mb is None:
            continue
        best = metrics.best_row(g)
        rows.append({
            "host": host,
            "threads": int(threads),
            "cache": cache_mb,
            "nb": int(best["nb"]),
            "gflops": float(best["GFlops"]),
        })

    if not rows:
        return None

    pts = pd.DataFrame(rows)
    xs = np.linspace(pts["cache"].min() * 0.7, pts["cache"].max() * 1.3, 100)
    theory = np.array([metrics.theory_nb(x) for x in xs])

    fig = go.Figure()
    # 実用域帯（25〜75%）
    fig.add_trace(go.Scatter(
        x=np.concatenate([xs, xs[::-1]]),
        y=np.concatenate([theory * 0.75, (theory * 0.25)[::-1]]),
        fill="toself", fillcolor="rgba(130,130,130,0.12)",
        line=dict(width=0), name="実用域 (25〜75%)", hoverinfo="skip",
    ))
    # 理論曲線
    fig.add_trace(go.Scatter(
        x=xs, y=theory, mode="lines",
        line=dict(dash="dash", color="gray"),
        name="理論値 nb≈√(cache/32)", hoverinfo="skip",
    ))
    # 実測点（スレッド別）
    for threads, g in pts.groupby("threads"):
        fig.add_trace(go.Scatter(
            x=g["cache"], y=g["nb"], mode="markers+text",
            text=g["host"], textposition="top center",
            marker=dict(size=13), name=f"{threads} threads",
            customdata=g["gflops"],
            hovertemplate=(
                "%{text}<br>cache/core=%{x:.2f} MB<br>"
                "best nb=%{y}<br>%{customdata:.1f} GFlop/s<extra></extra>"
            ),
        ))

    fig.update_layout(
        title="コアあたりキャッシュ量 × 最適タイルサイズ nb",
        xaxis_title="コアあたりキャッシュ量 (MB)",
        yaxis_title="最適 nb（GFlops最大）",
        height=600, margin=dict(l=60, r=20, t=50, b=50),
    )
    return fig


def compare_df(df: pd.DataFrame) -> pd.DataFrame:
    """host × threads の比較表（st.dataframe 用）。"""
    rows = []
    for (host, threads), g in df.groupby(["host", "threads"]):
        best = metrics.best_row(g)
        cpu = g["cpu_model"].iloc[0]
        rows.append({
            "ホスト": host,
            "ラベル": g["label"].iloc[0],
            "CPU": "—" if pd.isna(cpu) else cpu,
            "スレッド": int(threads),
            "ピーク GFlop/s": round(float(best["GFlops"]), 1),
            "最適 nb": int(best["nb"]),
            "最適 ib": int(best["ib"]),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["ホスト", "スレッド"]).reset_index(drop=True)
    return out


def line_fig(
    df: pd.DataFrame,
    threads: int,
    hosts: list[str] | None = None,
) -> go.Figure | None:
    """nb × GFlops 折れ線（各nbで最適ib選択、host別系列）。ホバーで値表示。"""
    sub = df[df["threads"] == threads]
    if hosts:
        sub = sub[sub["host"].isin(hosts)]
    if sub.empty:
        return None

    fig = go.Figure()
    for host, g in sub.groupby("host"):
        bb = metrics.best_per_nb(g)
        name = f"{g['label'].iloc[0]} [{host}]"
        fig.add_trace(go.Scatter(
            x=bb["nb"], y=bb["GFlops"], mode="lines+markers",
            name=name, marker=dict(size=5),
            hovertemplate=f"{host}<br>nb=%{{x}}<br>%{{y:.1f}} GFlop/s<extra></extra>",
        ))

    fig.update_layout(
        title=f"nb × GFlops（threads={threads}, 各nbで最適ib選択）",
        xaxis_title="nb (tile size)",
        yaxis_title="GFlop/s",
        height=600, margin=dict(l=60, r=20, t=50, b=50),
        hovermode="x unified",
    )
    return fig
