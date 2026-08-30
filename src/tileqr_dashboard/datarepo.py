"""tileQR_data リポジトリからデータを取得して統合テーブル用に整形する。

方針（ユーザ決定）:
  - tileQR_data を主データ源にする（inbox/HTTP受信は補助）。
  - 取得は起動時自動＋サイドバーの更新ボタン。
  - 識別単位(label)は config（例 aoba-b_s2_smt-off。sockets/SMT を区別）。

tileQR_data は derived/*.parquet を組み立て済みなので、**git は使わず**必要な
ファイルだけ HTTPS(raw)で落としてキャッシュする（軽量・コンテナに git 不要）。

  derived/qr_sweep.parquet   … tileqr フルQR（threads,size,nb,ib,GFlops,node,config,...）
  derived/ssrfb.parquet      … ssrfb カーネル（+Time_sec。node のみ、config 無し）
  machines.yaml              … architectures / configs / nodes（CPU諸元・対応キー）

machines.yaml の対応:
  configs[config].arch / nodes[node].arch → architectures[arch] から
  cpu / cache / cores / sockets を補完する（散布図・分析タブがそのまま動く）。
  nodes[node].source_key は sources.toml のキー、architectures[arch].dashboard_cpu は
  cpus.toml のキー（対応の明示。ここでは諸元は machines.yaml 側を正とする）。
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import pandas as pd

from . import paths

# 取得元。TILEQR_DATA_BASE で上書き可（private/別refに対応）。
_DEFAULT_BASE = "https://raw.githubusercontent.com/t21cs019/tileQR_data/main"

# 落とすファイル（リポジトリルートからの相対パス）
_FILES = ("derived/qr_sweep.parquet", "derived/ssrfb.parquet", "machines.yaml")


def base_url() -> str:
    return os.environ.get("TILEQR_DATA_BASE", _DEFAULT_BASE).rstrip("/")


def _download(url: str, dest: Path, timeout: float = 120.0) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "tileqr-dashboard"})
    token = os.environ.get("TILEQR_DATA_TOKEN")
    if token:  # private リポジトリ用（任意）
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)  # 原子的に差し替え（取得途中の破損を残さない）


def fetch() -> dict:
    """必要ファイルを tileQR_data から取得してキャッシュする。

    戻り値: {"fetched": [...], "errors": {rel: msg}}。
    一部失敗しても取得できたものは使う（machines.yaml だけ落ちる等に耐える）。
    """
    base = base_url()
    fetched: list[str] = []
    errors: dict[str, str] = {}
    for rel in _FILES:
        try:
            _download(f"{base}/{rel}", paths.DATA_REPO_DIR / rel)
            fetched.append(rel)
        except Exception as e:  # noqa: BLE001
            errors[rel] = str(e)
            print(f"  [datarepo] 取得失敗 {rel}: {e}")
    print(f"[datarepo] 取得 {len(fetched)}/{len(_FILES)} 件（{base}）")
    return {"fetched": fetched, "errors": errors}


def _load_machines() -> dict:
    mp = paths.DATA_REPO_DIR / "machines.yaml"
    if not mp.exists():
        return {}
    try:
        import yaml
    except ImportError:
        print("  [datarepo] pyyaml 未導入のため machines.yaml を読めません")
        return {}
    try:
        return yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        print(f"  [datarepo] machines.yaml 解析失敗: {e}")
        return {}


def _smt_to_tpc(smt) -> int | None:
    """machines.yaml の smt(on/off, bool化される) を threads_per_core に。"""
    if smt is True:
        return 2
    if smt is False:
        return 1
    return None


def _expand_arch(df: pd.DataFrame, arch_series: pd.Series, archs: dict) -> None:
    """arch 名の Series から architectures 諸元を df に横付けする（破壊的）。"""
    field_map = {
        "cpu_model": "cpu",
        "sockets": "sockets_physical",
        "cores_per_socket": "physical_cores_per_socket",
        "numa_nodes": "numa_nodes_total",
        "l1d_per_core_kb": "l1d_kb_per_core",
        "l2_per_core_kb": "l2_kb_per_core",
        "l3_per_socket_mb": "l3_mb_per_socket",
    }
    for out_col, yaml_key in field_map.items():
        table = {name: (a or {}).get(yaml_key) for name, a in archs.items()}
        df[out_col] = arch_series.map(table)


def build_runs() -> pd.DataFrame:
    """キャッシュ済みの tileQR_data から統合テーブル（inbox と同じ列）を作る。

    fetch() 済みであることが前提（未取得ならファイルが無く空 or 一部のみ）。
    ここではネットワークアクセスしない。
    """
    from .ingest import ALL_COLS  # 循環回避のため関数内 import

    machines = _load_machines()
    archs = machines.get("architectures", {}) or {}
    configs = machines.get("configs", {}) or {}
    nodes = machines.get("nodes", {}) or {}
    config_arch = {c: (v or {}).get("arch") for c, v in configs.items()}
    config_smt = {c: (v or {}).get("smt") for c, v in configs.items()}
    node_arch = {n: (v or {}).get("arch") for n, v in nodes.items()}
    node_srckey = {n: (v or {}).get("source_key") for n, v in nodes.items()}
    arch_smt_default = {n: (a or {}).get("smt_default") for n, a in archs.items()}

    frames: list[pd.DataFrame] = []

    # --- tileqr（qr_sweep.parquet。config 列あり）---
    sweep = paths.DATA_REPO_DIR / "derived" / "qr_sweep.parquet"
    if sweep.exists():
        d = pd.read_parquet(sweep)
        out = d[["threads", "size", "nb", "ib", "GFlops"]].copy()
        out["source_key"] = d["node"].map(node_srckey)
        out["host"] = d["node"]
        out["label"] = d["config"]                      # ← 識別単位は config
        arch_series = d["config"].map(config_arch)
        _expand_arch(out, arch_series, archs)
        out["threads_per_core"] = d["config"].map(config_smt).map(_smt_to_tpc)
        out["kind"] = "tileqr"
        out["origin"] = "tileQR_data"
        out["src_file"] = d.get("source_file")
        frames.append(out)

    # --- ssrfb（ssrfb.parquet。config 列なし → node から arch を引く）---
    ssrfb = paths.DATA_REPO_DIR / "derived" / "ssrfb.parquet"
    if ssrfb.exists():
        d = pd.read_parquet(ssrfb)
        out = d[["threads", "size", "nb", "ib", "GFlops"]].copy()
        out["source_key"] = d["node"].map(node_srckey)
        out["host"] = d["node"]
        out["label"] = d["node"]                         # ssrfb は config 無し
        arch_series = d["node"].map(node_arch)
        _expand_arch(out, arch_series, archs)
        out["threads_per_core"] = arch_series.map(arch_smt_default).map(_smt_to_tpc)
        out["kind"] = "ssrfb"
        out["origin"] = "tileQR_data"
        out["src_file"] = d.get("source_file")
        frames.append(out)

    if not frames:
        return pd.DataFrame(columns=ALL_COLS)

    table = pd.concat(frames, ignore_index=True)
    # 列順を統合テーブルに合わせる（欠けている列は NA で補う）
    for col in ALL_COLS:
        if col not in table.columns:
            table[col] = pd.NA
    return table[ALL_COLS]


def sync(include_inbox: bool = True) -> pd.DataFrame:
    """tileQR_data を取得し直し、統合テーブル(store/runs.parquet)を作り直す。"""
    fetch()
    from . import ingest  # 循環回避のため関数内 import
    return ingest.build_store(include_datarepo=True, include_inbox=include_inbox)
