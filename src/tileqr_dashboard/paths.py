"""プロジェクト内の主要パスを一元解決する。"""
from __future__ import annotations

from pathlib import Path

# src/tileqr_dashboard/paths.py → プロジェクトルート（tileQR_dashboard/）
ROOT = Path(__file__).resolve().parents[2]

CONFIG_DIR = ROOT / "config"
SOURCES_TOML = CONFIG_DIR / "sources.toml"
CPUS_TOML = CONFIG_DIR / "cpus.toml"

INBOX_DIR = ROOT / "inbox"
STORE_DIR = ROOT / "store"
OUTPUT_DIR = ROOT / "output"

RUNS_PARQUET = STORE_DIR / "runs.parquet"


def resolve(path_like: str | Path) -> Path:
    """相対パスはプロジェクトルート基準、絶対パスはそのまま返す。"""
    p = Path(path_like)
    return p if p.is_absolute() else (ROOT / p)
