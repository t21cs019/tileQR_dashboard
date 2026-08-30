"""tileQR ベンチマーク Web ダッシュボード（Streamlit + Plotly）。

起動: PYTHONPATH=src streamlit run dashboard/app.py
表示: http://localhost:8501

識別単位は host ではなく CPU(label) / threads / size。同じ組み合わせの
複数 host／試行は (nb, ib) ごとに平均して表示する（v0.4.0〜）。
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from tileqr_dashboard import datarepo, ingest, paths, plan
from tileqr_dashboard.config import load_sources
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


def _png_export_config(filename: str) -> dict:
    """図右上のカメラアイコンから落とせるPNGのファイル名・解像度・サイズを指定する。

    凡例を図の下に横並びにしている（line/scatter）ぶん、縦を広めに取る。
    """
    return {"toImageButtonOptions": {
        "format": "png", "filename": filename,
        "scale": 2, "width": 1400, "height": 850,
    }}


def _combo_options(df) -> list[str]:
    """データにある全 (label, threads, size) を "label · threads · size" 文字列で返す。"""
    combos_df = (
        df[["label", "threads", "size"]]
        .drop_duplicates()
        .sort_values(["label", "threads", "size"])
    )
    return [
        f"{lbl} · {int(th)} · {int(sz)}"
        for lbl, th, sz in combos_df.itertuples(index=False, name=None)
    ]


def _parse_combos(selected: list[str]) -> list[tuple[str, int, int]]:
    """"label · threads · size" 文字列を (label, threads, size) のタプルに戻す。"""
    return [
        (lbl, int(th), int(sz))
        for lbl, th, sz in (s.rsplit(" · ", 2) for s in selected)
    ]


_MANUAL_SUFFIXES = (".csv", ".meta.json")


def _manual_upload_ui() -> None:
    """サイドバー: ブラウザからCSV/メタを取り込む（手動アップロード）。"""
    with st.sidebar.expander("CSV手動アップロード", expanded=False):
        try:
            sources = load_sources()
        except Exception as e:  # noqa: BLE001
            st.error(f"sources.toml を読めません: {e}")
            return
        key = st.selectbox("取り込み先ソース", sorted(sources), key="ul_key")
        ups = st.file_uploader(
            "CSV / .meta.json（複数可）",
            accept_multiple_files=True, type=["csv", "json"], key="ul_files",
        )
        if st.button("取り込む", key="ul_go", use_container_width=True):
            if not ups:
                st.warning("ファイルを選んでください。")
                return
            src = sources[key]
            src.inbox.mkdir(parents=True, exist_ok=True)
            saved = 0
            for uf in ups:
                name = os.path.basename(uf.name)
                if name.endswith(_MANUAL_SUFFIXES):
                    (src.inbox / name).write_bytes(uf.getbuffer())
                    saved += 1
            if saved == 0:
                st.warning(".csv / .meta.json のみ取り込めます。")
                return
            ingest.build_store()
            st.cache_data.clear()
            st.success(f"{saved} 件を「{key}」に取り込みました。")
            st.rerun()


def _plan_editor(title: str, records: list[dict], cols: list[str], key: str):
    """1つの計測プラン表を編集エディタとして描画し、編集後DataFrameを返す。"""
    st.markdown(f"**{title}**")
    df_edit = pd.DataFrame(records, columns=cols)
    return st.data_editor(
        df_edit, key=key, num_rows="dynamic", use_container_width=True,
        hide_index=True,
        disabled=list(plan.READONLY_COLS),
        column_config={
            "status": st.column_config.TextColumn(
                "status", help="計測機の `plan scan` が自動更新（編集不可）"
            ),
            "coverage": st.column_config.TextColumn(
                "coverage", help="充足済み/全点（自動更新・編集不可）"
            ),
        },
    )


def _plan_tab() -> None:
    st.subheader("計測プラン（PROGRESS.md）")
    st.caption(
        "計測機（plasma-bench）からアップロードされた計測プランを閲覧・編集します。"
        "`status` / `coverage` は計測機の `plan scan` が results/ を走査して自動更新する"
        "読み取り専用列です。行の追加・note・skip はここで編集でき、計測機が pull して"
        "`plan run` に反映します。"
    )
    keys = plan.available_sources()
    if not keys:
        st.info(
            "まだ計測プランがありません。計測機から PROGRESS.md をアップロードしてください"
            "（plasma-bench: `bash scripts/sync_results.sh http`）。"
        )
        return

    key = st.selectbox("ソース", keys, key="plan_src")
    m = plan.load_for_source(key)
    if m is None:
        st.warning("PROGRESS.md を読み込めませんでした。")
        return

    ed_ssrfb = _plan_editor(
        "ssrfb", plan.bench_records(m.ssrfb, plan.SSRFB_COLS),
        plan.SSRFB_COLS, key="plan_ssrfb",
    )
    ed_tileqr = _plan_editor(
        "tileqr", plan.bench_records(m.tileqr, plan.TILEQR_COLS),
        plan.TILEQR_COLS, key="plan_tileqr",
    )
    ed_tuning = _plan_editor(
        "tuning", plan.tune_records(m.tuning),
        plan.TUNE_COLS, key="plan_tuning",
    )

    c1, c2 = st.columns([1, 3])
    if c1.button("保存", key="plan_save", use_container_width=True):
        new_m = plan.Manifest(
            ssrfb=plan.bench_from_records(ed_ssrfb.to_dict("records"), "ssrfb"),
            tileqr=plan.bench_from_records(ed_tileqr.to_dict("records"), "tileqr"),
            tuning=plan.tune_from_records(ed_tuning.to_dict("records")),
        )
        plan.save_for_source(key, new_m)
        st.success(
            f"「{key}」の PROGRESS.md を保存しました。計測機で "
            "`bash scripts/sync_plan.sh pull` すると反映されます。"
        )
    c2.caption(f"保管先: `{paths.plan_path(key)}`")

    with st.expander("PROGRESS.md（プレビュー）", expanded=False):
        st.code(plan.render(m), language="markdown")


st.title("tileQR ベンチマーク ダッシュボード")

with st.sidebar:
    st.header("操作")
    if st.button("tileQR_data から更新", use_container_width=True, type="primary"):
        with st.spinner("tileQR_data を取得して統合中..."):
            datarepo.sync()
        st.cache_data.clear()
        st.success("tileQR_data から更新しました。")
        st.rerun()
    if st.button("データ再読み込み", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.caption(
        "「tileQR_data から更新」で主データを取得し直します。"
        "「データ再読み込み」は取得済みデータの表示を最新化します。"
    )

_manual_upload_ui()

n_ssrfb = 0
try:
    df = get_data(_parquet_mtime())
except FileNotFoundError:
    df = pd.DataFrame()

# データ源(origin)フィルタ。tileQR_data（主）と inbox（補助）が混在するとき選べる。
if not df.empty and "origin" in df.columns:
    origin_vals = sorted(df["origin"].dropna().unique())
    if len(origin_vals) > 1:
        choice = st.sidebar.radio("データ源", ["すべて", *origin_vals], key="origin_filter")
        if choice != "すべて":
            df = df[df["origin"] == choice].copy()

# ssrfb はカーネル単体GFlops（別指標）なので tileqr のグラフから分離する。
# 旧 parquet（kind列なし）は全て tileqr 扱いにフォールバック。
if not df.empty and "kind" in df.columns:
    n_ssrfb = int((df["kind"] == "ssrfb").sum())
    df = df[df["kind"] == "tileqr"].copy()

has_data = not df.empty

if has_data:
    n_labels = df["label"].nunique()
    n_hosts = df["host"].nunique()
    n_rows = len(df)
    cap = f"{n_labels} CPU(label) / {n_hosts} ホスト / {n_rows:,} 計測点（tileqr）"
    if n_ssrfb:
        cap += f" ／ ssrfb {n_ssrfb:,} 点は別指標のため除外"
    st.caption(cap)
elif n_ssrfb:
    st.info(
        f"tileqr のデータがありません（ssrfb は {n_ssrfb:,} 点ありますが、"
        "カーネル単体GFlopsのためこれらのグラフには表示しません）。"
    )
else:
    st.info(
        "統合データがありません。inbox にCSVを置いて `bash run_sync.sh` を実行するか、"
        "サイドバーの「CSV手動アップロード」／受信APIで取り込んでください。"
        "（計測プランタブはデータが無くても使えます）"
    )

tab_overview, tab_heatmap, tab_line, tab_analysis, tab_plan = st.tabs(
    ["概要", "ヒートマップ", "nb-GFlops曲線", "分析", "計測プラン"]
)

with tab_plan:
    _plan_tab()

if not has_data:
    with tab_overview:
        st.info("データが無いため表示できません。")
    st.stop()

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
        st.plotly_chart(
            fig, use_container_width=True,
            config=_png_export_config("tileqr_heatmap"),
        )
    else:
        st.info("該当データがありません。")

combo_opts = _combo_options(df)

with tab_line:
    st.subheader("nb × GFlops 曲線（CPU比較）")
    line_selected = st.multiselect(
        "比較する (CPU・threads・size) の組み合わせ（複数選択可）",
        combo_opts, default=combo_opts, key="line_combos",
    )
    fig = plots.line_fig(df, _parse_combos(line_selected))
    if fig is not None:
        st.plotly_chart(
            fig, use_container_width=True,
            config=_png_export_config("tileqr_line"),
        )
    else:
        st.info("該当データがありません。")

with tab_analysis:
    st.subheader("キャッシュ量 × 最適タイルサイズ")
    sc_selected = st.multiselect(
        "比較する (CPU・threads・size) の組み合わせ（複数選択可）",
        combo_opts, default=combo_opts, key="sc_combos",
    )
    fig = plots.scatter_fig(df, _parse_combos(sc_selected))
    if fig is not None:
        st.plotly_chart(
            fig, use_container_width=True,
            config=_png_export_config("tileqr_scatter"),
        )
    else:
        st.info(
            "CPUキャッシュ情報（メタJSON または cpus.toml プリセット）を持つ"
            "組み合わせを選んでください。"
        )
