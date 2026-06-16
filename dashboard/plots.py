"""Plotly 図ビルダ（Streamlit から独立してテストできる純関数群）。

識別単位は host ではなく (label, threads, size)。同じ組み合わせの中で
複数 host／試行を (nb, ib) ごとに平均してから描画する（metrics.aggregate_runs）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from tileqr_dashboard import metrics


def heatmap_fig(df: pd.DataFrame, label: str, threads: int, size: int) -> go.Figure | None:
    """nb × ib の GFlops ヒートマップ。ホバーで nb/ib/GFlops を表示。

    同じ (label, threads, size) の複数 host／試行は (nb, ib) ごとに平均する。
    """
    agg = metrics.aggregate_runs(df, label, threads, size)
    if agg.empty:
        return None

    pivot = metrics.heatmap_pivot(agg)
    best = metrics.best_row(agg)

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
        title=f"{label}  threads={threads}  size={size}",
        xaxis_title="nb (tile size)",
        yaxis_title="ib (inner block size)",
        height=600,
        margin=dict(l=60, r=20, t=50, b=50),
    )
    return fig


def scatter_fig(df: pd.DataFrame, threads: int, size: int) -> go.Figure | None:
    """コアあたりキャッシュ量 × 最適 nb（threads, size固定。点は label 単位）。

    理論曲線と実用域を重ねる。
    """
    sub = df[(df["threads"] == threads) & (df["size"] == size)]
    if sub.empty:
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
    # 実測点（label別）
    fig.add_trace(go.Scatter(
        x=pts["cache"], y=pts["nb"], mode="markers+text",
        text=pts["label"], textposition="top center",
        marker=dict(size=13), name="実測",
        customdata=pts["gflops"],
        hovertemplate=(
            "%{text}<br>cache/core=%{x:.2f} MB<br>"
            "best nb=%{y}<br>%{customdata:.1f} GFlop/s<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=f"コアあたりキャッシュ量 × 最適タイルサイズ nb（threads={threads}, size={size}）",
        xaxis_title="コアあたりキャッシュ量 (MB)",
        yaxis_title="最適 nb（GFlops最大）",
        height=600, margin=dict(l=60, r=20, t=50, b=50),
    )
    return fig


def compare_df(df: pd.DataFrame) -> pd.DataFrame:
    """(label, threads, size) ごとの比較表（st.dataframe 用）。1組み合わせ=1行。"""
    rows = []
    combos = df[["label", "threads", "size"]].drop_duplicates()
    for _, combo in combos.iterrows():
        label, threads, size = combo["label"], int(combo["threads"]), int(combo["size"])
        agg = metrics.aggregate_runs(df, label, threads, size)
        if agg.empty:
            continue
        best = metrics.best_row(agg)
        sub = df[(df["label"] == label) & (df["threads"] == threads) & (df["size"] == size)]
        cpu = sub["cpu_model"].iloc[0]
        rows.append({
            "ラベル": label,
            "CPU": "—" if pd.isna(cpu) else cpu,
            "スレッド": threads,
            "サイズ": size,
            "ホスト数": int(sub["host"].nunique()),
            "ピーク GFlop/s": round(float(best["GFlops"]), 1),
            "最適 nb": int(best["nb"]),
            "最適 ib": int(best["ib"]),
        })
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["ラベル", "スレッド", "サイズ"]).reset_index(drop=True)
    return out


# 系列ごとの色を line と Max マーカーで揃えるための固定パレット（Plotly既定のD3配色）
_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


def line_fig(
    df: pd.DataFrame,
    combos: list[tuple[str, int, int]],
) -> go.Figure | None:
    """nb × GFlops 折れ線（各nbで最適ib選択）。

    combos: (label, threads, size) のリスト。各組を1系列として重ねる
    （host横断で (nb, ib) ごとに平均してから最適ib選択。metrics.aggregate_runs）。
    各系列のピークにマーカーを置き、Max XXX @ nb=YYY を注釈する（heatmapの赤点と同じ発想）。
    """
    fig = go.Figure()
    plotted = False
    for i, (label, threads, size) in enumerate(combos):
        agg = metrics.aggregate_runs(df, label, threads, size)
        if agg.empty:
            continue
        bb = metrics.best_per_nb(agg)
        color = _PALETTE[i % len(_PALETTE)]
        name = f"{label} · {threads} · {size}"

        fig.add_trace(go.Scatter(
            x=bb["nb"], y=bb["GFlops"], mode="lines+markers",
            name=name, marker=dict(size=5, color=color), line=dict(color=color),
            hovertemplate=f"{name}<br>nb=%{{x}}<br>%{{y:.1f}} GFlop/s<extra></extra>",
        ))

        best = metrics.best_row(bb)
        fig.add_trace(go.Scatter(
            x=[int(best["nb"])], y=[float(best["GFlops"])],
            mode="markers",
            marker=dict(
                size=13, color=color, symbol="star",
                line=dict(color="white", width=1.5),
            ),
            name=f"{name} Max", showlegend=False,
            hovertemplate=(
                f"{name}<br>Max {best['GFlops']:.1f} GFlop/s @ "
                f"nb={int(best['nb'])}<extra></extra>"
            ),
        ))
        fig.add_annotation(
            x=int(best["nb"]), y=float(best["GFlops"]),
            text=f"Max {best['GFlops']:.1f} @ nb={int(best['nb'])}",
            showarrow=True, arrowhead=2, ax=0, ay=-32,
            font=dict(size=10, color=color),
            bordercolor=color, borderwidth=1, bgcolor="white",
        )
        plotted = True

    if not plotted:
        return None

    fig.update_layout(
        title="nb × GFlops（host横断平均・各nbで最適ib選択・ピークにMax注釈）",
        xaxis_title="nb (tile size)",
        yaxis_title="GFlop/s",
        height=600, margin=dict(l=60, r=20, t=50, b=50),
        hovermode="closest",
    )
    return fig
