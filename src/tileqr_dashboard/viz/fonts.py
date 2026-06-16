"""matplotlib で日本語（NotoSansCJK）を使うための設定。"""
from __future__ import annotations

import matplotlib
from matplotlib import font_manager

_CANDIDATES = [
    "Noto Sans CJK JP",
    "Noto Sans CJK HK",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "IPAexGothic",
    "IPAGothic",
]

# ttc がデフォルトで登録されていない環境向けの探索パス
_TTC_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
]


def setup_japanese_font() -> str | None:
    """利用可能な日本語フォントを matplotlib に設定し、フォント名を返す。"""
    # 必要ならttcを明示登録
    for path in _TTC_PATHS:
        try:
            font_manager.fontManager.addfont(path)
        except (FileNotFoundError, RuntimeError):
            pass

    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CANDIDATES:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return name

    print("[warn] 日本語フォントが見つかりません。表のラベルが豆腐になる場合があります。")
    matplotlib.rcParams["axes.unicode_minus"] = False
    return None
