"""sources.toml を読み込み、ソース定義を返す。"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import paths


@dataclass
class Source:
    """1サーバ分のソース定義。"""

    key: str
    type: str  # "manual" | "onedrive"
    inbox: Path
    label: str
    remote: str | None = None
    cpu: str | None = None
    extra: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.inbox = paths.resolve(self.inbox)
        if self.type == "onedrive" and not self.remote:
            raise ValueError(
                f"source '{self.key}': type=onedrive には remote が必要です"
            )


_KNOWN_TYPES = {"manual", "onedrive"}


def load_sources(toml_path: Path | None = None) -> dict[str, Source]:
    """sources.toml をパースして {key: Source} を返す。"""
    toml_path = toml_path or paths.SOURCES_TOML
    if not toml_path.exists():
        raise FileNotFoundError(f"ソース定義が見つかりません: {toml_path}")

    with toml_path.open("rb") as f:
        data = tomllib.load(f)

    raw = data.get("sources", {})
    if not raw:
        raise ValueError(f"{toml_path} に [sources.*] がありません")

    sources: dict[str, Source] = {}
    for key, cfg in raw.items():
        stype = cfg.get("type")
        if stype not in _KNOWN_TYPES:
            raise ValueError(
                f"source '{key}': 未知の type='{stype}' "
                f"(使えるのは {sorted(_KNOWN_TYPES)})"
            )
        sources[key] = Source(
            key=key,
            type=stype,
            inbox=cfg["inbox"],
            label=cfg.get("label", key),
            remote=cfg.get("remote"),
            cpu=cfg.get("cpu"),
            extra={
                k: v
                for k, v in cfg.items()
                if k not in {"type", "inbox", "label", "remote", "cpu"}
            },
        )
    return sources
