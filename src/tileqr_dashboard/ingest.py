"""inbox 配下の CSV とメタJSON を読み、統合テーブル(parquet)を作る。

メタの解決順位:
  1. <csv名>.meta.json があればそれを使う（最優先）
  2. 無ければ source.cpu を cpus.toml のキーとして引く
     - 見つかれば model_name・sockets・cores・キャッシュまで全部補完
     - 見つからなければ source.cpu を model_name 文字列として扱う
       （従来動作。この場合キャッシュ等は空のまま）
  3. host はファイル名先頭トークン（例 par001_... → par001）か meta.host

メタが全く無いCSVでも、host / label / GFlops は埋まるので
ヒートマップや比較表は作れる（CPUキャッシュ依存の散布図だけ欠ける）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import paths
from .config import Source, load_cpus, load_sources

# CSV本体に必ずある列
_CSV_COLS = ["threads", "size", "nb", "ib", "GFlops"]

# メタ由来でテーブルに足す列（順序固定）
_META_COLS = [
    "source_key", "host", "label", "cpu_model",
    "sockets", "cores_per_socket", "threads_per_core", "numa_nodes",
    "l1d_per_core_kb", "l2_per_core_kb", "l3_total_mb",
    "src_file",
]


def _meta_path(csv_path: Path) -> Path:
    # par001_..._235252.csv → par001_..._235252.meta.json
    return csv_path.parent / (csv_path.stem + ".meta.json")


def resolve_meta(
    csv_path: Path, source: Source, cpus: dict[str, dict] | None = None
) -> dict:
    """1つのCSVに付与するメタ情報を解決する。

    cpus: cpus.toml の内容（{preset_key: 諸元dict}）。省略時は読み込む。
    """
    meta: dict = {}
    mp = _meta_path(csv_path)
    has_meta_file = mp.exists()
    if has_meta_file:
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  [warn] {mp.name}: JSON解析失敗 ({e}) — 無視します")
            meta = {}
            has_meta_file = False  # 解析失敗時はプリセット解決にフォールバック

    cpu = meta.get("cpu", {}) or {}
    host = meta.get("host") or csv_path.stem.split("_")[0]

    if not has_meta_file:
        # meta.json が無い（or 解析失敗）→ source.cpu を cpus.toml のキーとして引く
        if cpus is None:
            cpus = load_cpus()
        preset = cpus.get(source.cpu) if source.cpu else None
        if preset:
            cpu = preset
        # 見つからなければ cpu は空のまま → 下で source.cpu を model_name として使う

    return {
        "source_key": source.key,
        "host": host,
        "label": meta.get("label") or source.label,
        "cpu_model": cpu.get("model_name") or source.cpu,
        "sockets": cpu.get("sockets"),
        "cores_per_socket": cpu.get("cores_per_socket"),
        "threads_per_core": cpu.get("threads_per_core"),
        "numa_nodes": cpu.get("numa_nodes"),
        "l1d_per_core_kb": cpu.get("l1d_per_core_kb"),
        "l2_per_core_kb": cpu.get("l2_per_core_kb"),
        "l3_total_mb": cpu.get("l3_total_mb"),
        "src_file": csv_path.name,
    }


def _read_one(
    csv_path: Path, source: Source, cpus: dict[str, dict]
) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] {csv_path.name}: 読み込み失敗 ({e}) — スキップ")
        return None

    missing = [c for c in _CSV_COLS if c not in df.columns]
    if missing:
        print(f"  [warn] {csv_path.name}: 列不足 {missing} — スキップ")
        return None

    df = df[_CSV_COLS].copy()
    meta = resolve_meta(csv_path, source, cpus)
    for col, val in meta.items():
        df[col] = val
    return df


def collect_csvs(sources: dict[str, Source]) -> list[tuple[Path, Source]]:
    """全ソースの inbox から CSV を列挙する。"""
    found: list[tuple[Path, Source]] = []
    for source in sources.values():
        if not source.inbox.exists():
            continue
        for csv_path in sorted(source.inbox.glob("*.csv")):
            found.append((csv_path, source))
    return found


def build_store(sources: dict[str, Source] | None = None) -> pd.DataFrame:
    """inbox を走査して統合テーブルを作り、parquet に保存して返す。"""
    sources = sources or load_sources()
    items = collect_csvs(sources)

    if not items:
        print("[ingest] 取り込めるCSVがありません（inbox が空）")
        empty = pd.DataFrame(columns=_CSV_COLS + _META_COLS)
        return empty

    cpus = load_cpus()
    frames = []
    for csv_path, source in items:
        df = _read_one(csv_path, source, cpus)
        if df is not None:
            frames.append(df)
            print(f"  [ok] {source.key}: {csv_path.name} ({len(df)} 行)")

    if not frames:
        empty = pd.DataFrame(columns=_CSV_COLS + _META_COLS)
        return empty

    table = pd.concat(frames, ignore_index=True)
    table = table[_CSV_COLS + _META_COLS]

    paths.STORE_DIR.mkdir(parents=True, exist_ok=True)
    table.to_parquet(paths.RUNS_PARQUET, index=False)
    print(
        f"[ingest] 統合完了: {len(table)} 行 / "
        f"{table['host'].nunique()} ホスト → {paths.RUNS_PARQUET}"
    )
    return table


def load_store() -> pd.DataFrame:
    """保存済みの統合テーブルを読む。無ければ空。"""
    if not paths.RUNS_PARQUET.exists():
        raise FileNotFoundError(
            f"{paths.RUNS_PARQUET} がありません。先に sync_pull を実行してください。"
        )
    return pd.read_parquet(paths.RUNS_PARQUET)
