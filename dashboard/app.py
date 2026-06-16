"""tileQR ベンチマーク Web ダッシュボード（Streamlit + Plotly）。

起動: PYTHONPATH=src streamlit run dashboard/app.py
表示: http://localhost:8501

識別単位は host ではなく CPU(label) / threads / size。同じ組み合わせの
複数 host／試行は (nb, ib) ごとに平均して表示する（v0.4.0〜）。
"""
from __future__ import annotations

import os

import streamlit as st

from tileqr_dashboard import paths
from tileqr_dashboard.ingest import load_store

import plots  # 同ディレクトリ

st.set_page_config(page_title="tileQR Dashboard", layout="wide")


@st.cache_data
def get_data(_mtime: float):
    """parquet を読む。_mtime が変わるとキャッシュが無効化される。"""
    return load_store()


def _parquet_mtime() -> float:
    p = paths.RUNS_PARQUET
    return p.stat().st_mtime if p.exists() else 0.0


st.title("tileQR ベンチマーク ダッシュボード")

with st.sidebar:
    st.header("操作")
    if st.button("データ再読み込み", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption("`run_sync.sh` で取り込んだ後に押すと最新化されます。")

try:
    df = get_data(_parquet_mtime())
except FileNotFoundError:
    st.warning(
        "統合データがありません。先に `bash run_sync.sh` を実行してください。"
    )
    st.stop()

if df.empty:
    st.warning("データが空です。inbox にCSVを置いて `run_sync.sh` を実行してください。")
    st.stop()

n_labels = df["label"].nunique()
n_hosts = df["host"].nunique()
n_rows = len(df)
st.caption(f"{n_labels} CPU(label) / {n_hosts} ホスト / {n_rows:,} 計測点")

tab_overview, tab_heatmap, tab_line, tab_analysis = st.tabs(
    ["概要", "ヒートマップ", "nb-GFlops曲線", "分析"]
)

with tab_overview:
    st.subheader("CPU別 ピーク性能（label × threads × size）")
    st.dataframe(plots.compare_df(df), use_container_width=True, hide_index=True)

with tab_heatmap:
    st.subheader("nb × ib ヒートマップ")
    c1, c2, c3 = st.columns(3)
    label_opts = sorted(df["label"].dropna().unique())
    hm_label = c1.selectbox("CPU (label)", label_opts, key="hm_label")

    sub_l = df[df["label"] == hm_label]
    thread_opts = sorted(sub_l["threads"].unique())
    hm_threads = c2.selectbox("スレッド数", thread_opts, key="hm_threads")

    sub_lt = sub_l[sub_l["threads"] == hm_threads]
    size_opts = sorted(sub_lt["size"].unique())
    hm_size = c3.selectbox("size", size_opts, key="hm_size")

    fig = plots.heatmap_fig(df, hm_label, int(hm_threads), int(hm_size))
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("該当データがありません。")

with tab_line:
    st.subheader("nb × GFlops 曲線（CPU比較）")
    c1, c2 = st.columns(2)
    line_thread_opts = sorted(df["threads"].unique())
    line_threads = c1.selectbox("スレッド数", line_thread_opts, key="line_threads")
    line_size_opts = sorted(df[df["threads"] == line_threads]["size"].unique())
    line_size = c2.selectbox("size", line_size_opts, key="line_size")

    line_label_opts = sorted(
        df[(df["threads"] == line_threads) & (df["size"] == line_size)]["label"]
        .dropna()
        .unique()
    )
    line_labels = st.multiselect(
        "CPU(label)（複数選択可）", line_label_opts, default=line_label_opts
    )
    fig = plots.line_fig(df, int(line_threads), int(line_size), line_labels or None)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("該当データがありません。")

with tab_analysis:
    st.subheader("キャッシュ量 × 最適タイルサイズ")
    c1, c2 = st.columns(2)
    sc_thread_opts = sorted(df["threads"].unique())
    sc_threads = c1.selectbox("スレッド数", sc_thread_opts, key="sc_threads")
    sc_size_opts = sorted(df[df["threads"] == sc_threads]["size"].unique())
    sc_size = c2.selectbox("size", sc_size_opts, key="sc_size")

    fig = plots.scatter_fig(df, int(sc_threads), int(sc_size))
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(
            "CPUキャッシュ情報（メタJSON または cpus.toml プリセット）を持つ"
            "label がこの threads/size にありません。"
        )
