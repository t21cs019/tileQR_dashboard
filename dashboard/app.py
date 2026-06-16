"""tileQR ベンチマーク Web ダッシュボード（Streamlit + Plotly）。

起動: PYTHONPATH=src streamlit run dashboard/app.py
表示: http://localhost:8501
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

n_hosts = df["host"].nunique()
n_rows = len(df)
st.caption(f"{n_hosts} ホスト / {n_rows:,} 計測点")

tab_overview, tab_host, tab_analysis = st.tabs(["概要", "ホスト詳細", "分析"])

with tab_overview:
    st.subheader("CPU別 ピーク性能")
    st.dataframe(plots.compare_df(df), use_container_width=True, hide_index=True)

with tab_host:
    st.subheader("nb × ib ヒートマップ")
    c1, c2 = st.columns(2)
    hosts = sorted(df["host"].unique())
    host = c1.selectbox("ホスト", hosts)
    thread_opts = sorted(df[df["host"] == host]["threads"].unique())
    threads = c2.selectbox("スレッド数", thread_opts)

    fig = plots.heatmap_fig(df, host, int(threads))
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("該当データがありません。")

with tab_analysis:
    st.subheader("キャッシュ量 × 最適タイルサイズ")
    fig = plots.scatter_fig(df)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(
            "CPUキャッシュ情報（メタJSON）を持つホストがありません。"
            "CSVと同名の .meta.json を inbox に置くと表示されます。"
        )
