"""取得アダプタ — ソースのデータを inbox に用意する責務を持つ。

各アダプタは pull(source) を実装し、inbox 配下に CSV(と任意で meta.json)
が揃った状態にする。ingest はその後 inbox を走査するだけでよい。
"""
from __future__ import annotations

from ..config import Source
from . import manual, onedrive

_DISPATCH = {
    "manual": manual.pull,
    "onedrive": onedrive.pull,
}


def pull(source: Source) -> None:
    """source.type に応じたアダプタで inbox を更新する。"""
    fn = _DISPATCH.get(source.type)
    if fn is None:
        raise ValueError(f"未対応のアダプタ type: {source.type}")
    fn(source)
