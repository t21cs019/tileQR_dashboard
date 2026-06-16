"""manual アダプタ — 人手で inbox に置かれたファイルを使う。

ネットワーク処理は無し。inbox フォルダが無ければ作成し、
中身の件数を報告するだけ。
"""
from __future__ import annotations

from ..config import Source


def pull(source: Source) -> None:
    source.inbox.mkdir(parents=True, exist_ok=True)
    n = len(list(source.inbox.glob("*.csv")))
    if n == 0:
        print(
            f"  [manual] {source.key}: {source.inbox} は空です。"
            f"NextcloudからDLしたCSVをここに置いてください。"
        )
    else:
        print(f"  [manual] {source.key}: {n} 件のCSVを検出")
