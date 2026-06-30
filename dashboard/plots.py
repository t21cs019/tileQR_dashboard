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


_AOBA_COLOR = "#e07b00"
_OTHER_COLOR = "steelblue"


def scatter_fig(df: pd.DataFrame, combos: list[tuple[str, int, int]]) -> go.Figure | None:
    """nb × スレッドあたりキャッシュ量。

    combos: (label, threads, size) のリスト。各組を1点としてプロットする
    （line_fig と同じ選び方。host横断で集約してから最適nbを選ぶ）。
    理論帯 nb≈√(cache×ratio/32) の50〜150%帯と100%ラインを重ねる。
    label に "AOBA" を含むものは別色・別マーカー（cache_vs_tile_v3.py のスタイル）。
    """
    rows = []
    for label, threads, size in combos:
        sub = df[(df["label"] == label) & (df["threads"] == threads) & (df["size"] == size)]
        if sub.empty:
            continue
        cache_kb = metrics.cache_per_thread_kb(sub.iloc[0], threads)
        if cache_kb is None:
            continue
        agg = metrics.aggregate_runs(df, label, threads, size)
        if agg.empty:
            continue
        bb = metrics.best_per_nb(agg)
        best = metrics.best_row(bb)
        rows.append({
            "label": label,
            "threads": threads,
            "size": size,
            "cache_kb": cache_kb,
            "nb": int(best["nb"]),
            "gflops": float(best["GFlops"]),
        })

    if not rows:
        return None

    pts = pd.DataFrame(rows)
    # ラベルが重ならないよう、点ごとに上下交互にテキスト位置をずらす
    pts["text_pos"] = [
        "top center" if i % 2 == 0 else "bottom center" for i in range(len(pts))
    ]
    cache_range = np.linspace(pts["cache_kb"].min() * 0.7, pts["cache_kb"].max() * 1.3, 200)
    nb_50 = np.array([metrics.theory_nb_from_cache_kb(c, 0.50) for c in cache_range])
    nb_100 = np.array([metrics.theory_nb_from_cache_kb(c, 1.00) for c in cache_range])
    nb_150 = np.array([metrics.theory_nb_from_cache_kb(c, 1.50) for c in cache_range])

    fig = go.Figure()
    # 理論帯（50〜150%使用）。Plotlyはx方向のfillなので、左端=nb_50(下→上)・右端=nb_150(上→下)の
    # 輪郭で囲んで fill_betweenx 相当を作る。
    fig.add_trace(go.Scatter(
        x=np.concatenate([nb_50, nb_150[::-1]]),
        y=np.concatenate([cache_range, cache_range[::-1]]),
        fill="toself", fillcolor="rgba(128,128,128,0.22)",
        line=dict(width=0), name="理論帯 (50〜150% 使用)", hoverinfo="skip",
    ))
    # 100%ライン
    fig.add_trace(go.Scatter(
        x=nb_100, y=cache_range, mode="lines",
        line=dict(color="red", width=2),
        name="100% 使用ライン", hoverinfo="skip",
    ))

    # 実測点（AOBA系は別色・別マーカー）
    is_aoba = pts["label"].str.contains("AOBA")
    for subset, color, symbol, legend_name in (
        (pts[~is_aoba], _OTHER_COLOR, "circle", "その他 CPU(label)"),
        (pts[is_aoba], _AOBA_COLOR, "diamond", "AOBA"),
    ):
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset["nb"], y=subset["cache_kb"], mode="markers+text",
            text=[
                f"{r.label} · {r.threads} · {r.size}" for r in subset.itertuples()
            ],
            textposition=subset["text_pos"].tolist(),
            marker=dict(size=14, color=color, symbol=symbol, line=dict(color="white", width=1)),
            name=legend_name,
            customdata=subset["gflops"],
            hovertemplate=(
                "%{text}<br>nb=%{x}<br>cache/thread=%{y:.0f} KB<br>"
                "%{customdata:.1f} GFlop/s<extra></extra>"
            ),
        ))

    fig.update_layout(
        title="nb × スレッドあたりキャッシュ量（選択した組み合わせを比較）",
        xaxis_title="Tile Size (nb)",
        yaxis_title="Cache Size / Thread (KB)",
        height=600,
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=130),
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
        height=600,
        legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
        margin=dict(l=60, r=40, t=60, b=130),
        hovermode="closest",
    )
    return fig
