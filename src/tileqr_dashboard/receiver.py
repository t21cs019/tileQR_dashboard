"""受信API — 計測機（plasma-bench）からCSV・メタ・計測プランを受け取る。

ZimaOS 上でダッシュボードと並走する軽量な HTTP エンドポイント。
計測機の `scripts/sync_results.sh http` がここへ POST し、CSV は各ソースの
inbox に着地して統合テーブル(store/runs.parquet)を自動再構築する。
計測プラン(PROGRESS.md)は plan/<key>/ に保管し、ダッシュボードで編集した版を
計測機が GET で取り戻して `plan run` に反映する（往復同期）。

エンドポイント:
  GET  /health                 死活監視（ZimaOS/compose の healthcheck 用）
  GET  /sources                取り込み可能なソースキー一覧
  POST /upload/{source_key}    CSV(+ .meta.json) を multipart で受信 → inbox → 再取込
  GET  /plan/{source_key}      PROGRESS.md を返す（計測機が pull）
  POST /plan/{source_key}      PROGRESS.md を受信して保存（計測機が push）
  GET  /plan                   PROGRESS.md を持つソース一覧

任意で共有トークン認証（環境変数 DASHBOARD_TOKEN）。設定時は書き込み系
（/upload・POST /plan）に `X-Auth-Token: <token>` ヘッダを要求する。

起動: PYTHONPATH=src uvicorn tileqr_dashboard.receiver:app --host 0.0.0.0 --port 8502
"""
from __future__ import annotations

import os
from typing import List

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse

from . import ingest, paths
from .config import Source, load_sources

# 受け付ける拡張子（それ以外は無視して安全側に倒す）
_ALLOWED_SUFFIXES = (".csv", ".meta.json")

app = FastAPI(
    title="tileQR Dashboard 受信API",
    summary="計測機からCSV・メタ・計測プランを受け取る",
)


def _require_token(x_auth_token: str | None = Header(default=None)) -> None:
    """DASHBOARD_TOKEN が設定されていれば書き込み系でトークンを検証する。"""
    expected = os.environ.get("DASHBOARD_TOKEN")
    if not expected:
        return  # 未設定なら認証なし（LAN内・Tailscale前提の運用）
    if x_auth_token != expected:
        raise HTTPException(status_code=401, detail="トークンが一致しません")


def _get_source(source_key: str) -> Source:
    sources = load_sources()
    src = sources.get(source_key)
    if src is None:
        raise HTTPException(
            status_code=404,
            detail=f"未知のソース '{source_key}'。既知: {sorted(sources)}",
        )
    return src


def _safe_name(filename: str | None) -> str | None:
    """パス要素を除いた basename を返し、許可拡張子以外は弾く。"""
    if not filename:
        return None
    name = os.path.basename(filename)
    if not name or name.startswith("."):
        return None
    if not name.endswith(_ALLOWED_SUFFIXES):
        return None
    return name


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/sources")
def sources() -> dict:
    return {"sources": sorted(load_sources())}


@app.post("/upload/{source_key}")
async def upload(
    source_key: str,
    files: List[UploadFile] = File(default=[]),
    _: None = Depends(_require_token),
) -> dict:
    """CSV(+ .meta.json) を受信して inbox に置き、統合テーブルを再構築する。"""
    src = _get_source(source_key)
    src.inbox.mkdir(parents=True, exist_ok=True)

    if not files:
        raise HTTPException(status_code=400, detail="ファイルがありません")

    saved: list[str] = []
    skipped: list[str] = []
    for uf in files:
        name = _safe_name(uf.filename)
        if name is None:
            skipped.append(uf.filename or "(no name)")
            continue
        data = await uf.read()
        (src.inbox / name).write_bytes(data)
        saved.append(name)

    if not saved:
        raise HTTPException(
            status_code=400,
            detail=f"保存できるファイルがありません（.csv/.meta.json のみ）。skipped={skipped}",
        )

    # inbox が更新されたので全ソースを走査して store を作り直す
    # （ダッシュボードは parquet の mtime でキャッシュを無効化して最新化する）
    ingest.build_store()
    return {"source": source_key, "saved": saved, "skipped": skipped}


@app.get("/plan")
def plan_list() -> dict:
    from . import plan as plan_mod
    return {"sources": plan_mod.available_sources()}


@app.get("/plan/{source_key}", response_class=PlainTextResponse)
def plan_get(source_key: str) -> str:
    """ソースの PROGRESS.md を返す（計測機が編集済み版を pull する）。"""
    p = paths.plan_path(source_key)
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail=f"'{source_key}' の PROGRESS.md がありません",
        )
    return p.read_text(encoding="utf-8")


@app.post("/plan/{source_key}", response_class=PlainTextResponse)
async def plan_put(
    source_key: str,
    request: Request,
    _: None = Depends(_require_token),
) -> str:
    """PROGRESS.md を受信して plan/<key>/PROGRESS.md に保存する。

    本文はプレーンな Markdown（PROGRESS.md そのもの）を受け取る。
    """
    body = (await request.body()).decode("utf-8")
    if not body.strip():
        raise HTTPException(status_code=400, detail="本文が空です")
    p = paths.plan_path(source_key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return "ok"
