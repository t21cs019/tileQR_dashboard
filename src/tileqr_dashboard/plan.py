"""計測プラン（plasma-bench の `plan/PROGRESS.md`）の読み書き。

plasma-bench 側 `src/plasma_perf/plan/manifest.py` と **同じフォーマット**で
PROGRESS.md をパース／レンダリングする。ダッシュボードはこのモジュールで

  1. HTTP受信でアップロードされた各ソースの PROGRESS.md を読み（閲覧）、
  2. 計画列（status/coverage 以外）と note をブラウザ上で編集し、
  3. 同じフォーマットで書き戻す（計測機が pull して `plan run` に反映）。

status / coverage は計測機側の `plan scan` が results/ を走査して自動更新する列
なので、ダッシュボードでは**読み取り専用**として扱う（編集しても計測機側の
再スキャンで上書きされる）。フォーマット互換を壊さないため、行のパース／整形は
plasma-bench 実装をそのまま移植している。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from . import paths

_HEADER = """# 計測進捗（plasma-perf）

<!--
  このファイルは `python -m plasma_perf plan scan` が status/coverage を自動更新します。
  計画列（status/coverage 以外）と note 列は手動編集できます。
  行の追加は `plan add` が簡単です（例: plan add ssrfb --sizes 4096,8192 --threads 1）。
  note に skip / manual と書くと `plan run` はその行を実行しません。
  nb は "min-max"（例 32-512）で書きます。
-->
"""

SSRFB_COLS = ["size", "threads", "n_it", "nb", "ib_min", "step", "trials",
              "status", "coverage", "note"]
TILEQR_COLS = ["size", "threads", "nb", "ib_min", "step", "trials",
               "status", "coverage", "note"]
TUNE_COLS = ["mode", "size", "threads", "n_trials", "counts",
             "status", "coverage", "note"]

# ダッシュボードで編集させない（計測機の plan scan が算出する）列
READONLY_COLS = ("status", "coverage")


@dataclass
class BenchRow:
    kind: str            # "ssrfb" | "tileqr"
    size: int
    threads: int
    nb_min: int
    nb_max: int
    ib_min: int
    step: int
    trials: int
    n_it: Optional[int] = None   # ssrfb のみ
    status: str = "?"
    coverage: str = ""
    note: str = ""

    @property
    def nb(self) -> str:
        return f"{self.nb_min}-{self.nb_max}"


@dataclass
class TuneRow:
    mode: str            # normal | select | ssrfb
    size: int
    threads: int
    n_trials: int
    counts: int
    status: str = "?"
    coverage: str = ""
    note: str = ""


@dataclass
class Manifest:
    ssrfb: List[BenchRow] = field(default_factory=list)
    tileqr: List[BenchRow] = field(default_factory=list)
    tuning: List[TuneRow] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.ssrfb or self.tileqr or self.tuning)


# --------------------------------------------------------------------------
# パース（plasma-bench manifest.py と同じ規約）
# --------------------------------------------------------------------------
def _parse_nb(text: str):
    text = text.strip()
    if "-" in text:
        a, b = text.split("-", 1)
        return int(a), int(b)
    v = int(text)
    return v, v


def _split_row(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table_rows(lines: List[str], start: int):
    """start 以降の連続する '|' 行（ヘッダ+区切り+データ）からデータ行を返す。"""
    rows = []
    i = start
    seen = 0
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        seen += 1
        if seen > 2:  # 1=ヘッダ, 2=区切り, 3以降=データ
            rows.append(lines[i])
        i += 1
    return rows, i


def parse(text: str) -> Manifest:
    lines = text.splitlines()
    m = Manifest()
    i = 0
    section = None
    while i < len(lines):
        line = lines[i].strip()
        low = line.lower()
        if low.startswith("## "):
            name = low[3:].strip()
            section = name if name in ("ssrfb", "tileqr", "tuning") else None
            i += 1
            continue
        if section and line.startswith("|"):
            data, nxt = _table_rows(lines, i)
            for d in data:
                try:
                    _parse_into(m, section, _split_row(d))
                except (ValueError, IndexError):
                    continue  # 壊れた行は飛ばす
            i = nxt
            section = None
            continue
        i += 1
    return m


def _parse_into(m: Manifest, section: str, c: List[str]) -> None:
    if section == "ssrfb":
        nb_min, nb_max = _parse_nb(c[3])
        m.ssrfb.append(BenchRow(
            kind="ssrfb", size=int(c[0]), threads=int(c[1]),
            n_it=int(c[2]), nb_min=nb_min, nb_max=nb_max,
            ib_min=int(c[4]), step=int(c[5]), trials=int(c[6]),
            status=c[7] if len(c) > 7 else "?",
            coverage=c[8] if len(c) > 8 else "",
            note=c[9] if len(c) > 9 else "",
        ))
    elif section == "tileqr":
        nb_min, nb_max = _parse_nb(c[2])
        m.tileqr.append(BenchRow(
            kind="tileqr", size=int(c[0]), threads=int(c[1]),
            nb_min=nb_min, nb_max=nb_max, ib_min=int(c[3]),
            step=int(c[4]), trials=int(c[5]),
            status=c[6] if len(c) > 6 else "?",
            coverage=c[7] if len(c) > 7 else "",
            note=c[8] if len(c) > 8 else "",
        ))
    elif section == "tuning":
        m.tuning.append(TuneRow(
            mode=c[0], size=int(c[1]), threads=int(c[2]),
            n_trials=int(c[3]), counts=int(c[4]),
            status=c[5] if len(c) > 5 else "?",
            coverage=c[6] if len(c) > 6 else "",
            note=c[7] if len(c) > 7 else "",
        ))


# --------------------------------------------------------------------------
# レンダリング（桁揃え。plasma-bench manifest.py と同じ）
# --------------------------------------------------------------------------
def _render_table(cols: List[str], rows: List[List[str]]) -> str:
    widths = [len(c) for c in cols]
    for r in rows:
        for j, cell in enumerate(r):
            widths[j] = max(widths[j], len(cell))

    def fmt(cells):
        return "| " + " | ".join(
            cell.ljust(widths[j]) for j, cell in enumerate(cells)
        ) + " |"

    out = [fmt(cols),
           "| " + " | ".join("-" * widths[j] for j in range(len(cols))) + " |"]
    out += [fmt(r) for r in rows]
    return "\n".join(out)


def _bench_cells(row: BenchRow, cols: List[str]) -> List[str]:
    values = {
        "size": str(row.size), "threads": str(row.threads),
        "n_it": "" if row.n_it is None else str(row.n_it),
        "nb": row.nb, "ib_min": str(row.ib_min), "step": str(row.step),
        "trials": str(row.trials), "status": row.status,
        "coverage": row.coverage, "note": row.note,
    }
    return [values[c] for c in cols]


def _tune_cells(row: TuneRow) -> List[str]:
    return [row.mode, str(row.size), str(row.threads), str(row.n_trials),
            str(row.counts), row.status, row.coverage, row.note]


def render(m: Manifest) -> str:
    parts = [_HEADER, "## ssrfb", "",
             _render_table(SSRFB_COLS, [_bench_cells(r, SSRFB_COLS) for r in m.ssrfb]),
             "", "## tileqr", "",
             _render_table(TILEQR_COLS, [_bench_cells(r, TILEQR_COLS) for r in m.tileqr]),
             "", "## tuning", "",
             _render_table(TUNE_COLS, [_tune_cells(r) for r in m.tuning]),
             ""]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# ダッシュボード向けヘルパ（table ⇄ list[dict]）
# --------------------------------------------------------------------------
def bench_records(rows: List[BenchRow], cols: List[str]) -> List[dict]:
    """BenchRow のリストを st.data_editor 用の list[dict] に変換する。"""
    return [dict(zip(cols, _bench_cells(r, cols))) for r in rows]


def tune_records(rows: List[TuneRow]) -> List[dict]:
    return [dict(zip(TUNE_COLS, _tune_cells(r))) for r in rows]


def _cell(value) -> str:
    """data_editor 由来のセルを文字列化する。None / NaN / 欠損は空文字に落とす。

    st.data_editor は動的行の未入力セルを None や float('nan') で返すため、
    そのまま str() すると "None" / "nan" になってしまう。ここで正規化する。
    """
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    s = str(value).strip()
    return "" if s.lower() in ("nan", "none", "<na>") else s


def _to_int(value, default: int = 0) -> int:
    s = _cell(value)
    try:
        return int(float(s)) if s else default
    except (ValueError, TypeError):
        return default


def bench_from_records(records: List[dict], kind: str) -> List[BenchRow]:
    """編集済みの list[dict] から BenchRow を復元する（ssrfb/tileqr 共通）。

    nb か size が空の行（data_editor で追加された空行など）はスキップする。
    """
    out: List[BenchRow] = []
    for rec in records:
        nb = _cell(rec.get("nb"))
        if not nb or not _cell(rec.get("size")):
            continue
        try:
            nb_min, nb_max = _parse_nb(nb)
        except ValueError:
            continue
        n_it = None
        if kind == "ssrfb":
            raw = _cell(rec.get("n_it"))
            n_it = _to_int(raw) if raw else None
        out.append(BenchRow(
            kind=kind,
            size=_to_int(rec.get("size")),
            threads=_to_int(rec.get("threads")),
            nb_min=nb_min, nb_max=nb_max,
            ib_min=_to_int(rec.get("ib_min"), 8),
            step=_to_int(rec.get("step"), 4),
            trials=_to_int(rec.get("trials"), 5),
            n_it=n_it,
            status=_cell(rec.get("status")) or "?",
            coverage=_cell(rec.get("coverage")),
            note=_cell(rec.get("note")),
        ))
    return out


def tune_from_records(records: List[dict]) -> List[TuneRow]:
    out: List[TuneRow] = []
    for rec in records:
        mode = _cell(rec.get("mode"))
        if not mode:
            continue
        out.append(TuneRow(
            mode=mode,
            size=_to_int(rec.get("size")),
            threads=_to_int(rec.get("threads")),
            n_trials=_to_int(rec.get("n_trials"), 25),
            counts=_to_int(rec.get("counts"), 10),
            status=_cell(rec.get("status")) or "?",
            coverage=_cell(rec.get("coverage")),
            note=_cell(rec.get("note")),
        ))
    return out


# --------------------------------------------------------------------------
# I/O（ソース単位: plan/<source_key>/PROGRESS.md）
# --------------------------------------------------------------------------
def available_sources() -> List[str]:
    """PROGRESS.md を持つソースキーの一覧（plan/*/PROGRESS.md）。"""
    if not paths.PLAN_DIR.exists():
        return []
    keys = [
        d.name for d in sorted(paths.PLAN_DIR.iterdir())
        if d.is_dir() and (d / "PROGRESS.md").exists()
    ]
    return keys


def load_for_source(source_key: str) -> Optional[Manifest]:
    """ソースの PROGRESS.md を読む。無ければ None。"""
    p = paths.plan_path(source_key)
    if not p.exists():
        return None
    return parse(p.read_text(encoding="utf-8"))


def save_for_source(source_key: str, m: Manifest) -> None:
    """ソースの PROGRESS.md を書き戻す（桁揃え）。"""
    p = paths.plan_path(source_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render(m), encoding="utf-8")
