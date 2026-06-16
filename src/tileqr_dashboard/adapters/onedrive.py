"""onedrive アダプタ — rclone でリモートから inbox へ差分pullする。

rclone がインストール済みで、対象のリモート（例 'onedrive:'）が
`rclone config` で設定済みであることを前提とする。
"""
from __future__ import annotations

import shutil
import subprocess

from ..config import Source


def _rclone_available() -> bool:
    return shutil.which("rclone") is not None


def pull(source: Source) -> None:
    source.inbox.mkdir(parents=True, exist_ok=True)

    if not _rclone_available():
        print(
            f"  [onedrive] {source.key}: rclone が見つかりません。"
            f"スキップします（手動でinboxに置けば取り込めます）。"
        )
        return

    # copy は差分のみ転送。CSVとmeta.jsonだけに絞る。
    cmd = [
        "rclone", "copy",
        source.remote, str(source.inbox),
        "--include", "*.csv",
        "--include", "*.meta.json",
        "--verbose",
    ]
    print(f"  [onedrive] {source.key}: rclone copy {source.remote} -> {source.inbox}")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600
        )
    except subprocess.TimeoutExpired:
        print(f"  [onedrive] {source.key}: タイムアウト（600s）")
        return

    if result.returncode != 0:
        print(f"  [onedrive] {source.key}: rclone 失敗 (rc={result.returncode})")
        if result.stderr:
            print("    " + result.stderr.strip().splitlines()[-1])
    else:
        n = len(list(source.inbox.glob("*.csv")))
        print(f"  [onedrive] {source.key}: 同期完了（{n} 件のCSV）")
