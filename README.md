# tileQR_dashboard

PLASMA tileQR（dgeqrf）ベンチマーク結果を、複数サーバから**1台のPC（WSL2）に集約して可視化**するためのダッシュボード。
計測側リポジトリ `optuna_tileQR` とは独立して動く。

## 役割分担

```
計測層（AOBA-B / calc / 将来サーバ）   →  CSV(+任意でmeta.json) を出力
        │  転送（manual / onedrive）
        ▼
集約・可視化層（このリポジトリ, WSL2上）  →  統合・グラフ化
```

- **取得層**：サーバごとに取得方法を選べる（`manual` 手動投入 / `onedrive` rcloneで自動pull）。経路はアダプタとして分離してあり、将来 `ssh` 等を足せる。
- **データストア**：全サーバのCSVとメタを `store/runs.parquet` に統合。
- **可視化層**：ヒートマップ・散布図・CPU比較表。

メタJSONが無いCSVでも、ホスト名・GFlops は埋まるのでヒートマップと比較表は作れる（キャッシュ依存の散布図だけメタが必要）。

## ディレクトリ構成

```
tileQR_dashboard/
├── config/sources.toml          # ソース定義（サーバごと）
├── inbox/
│   ├── onedrive/<key>/          # rcloneが落とす先
│   └── manual/<key>/            # 手動投入（NextcloudからDLしたCSV）
├── store/runs.parquet           # 統合テーブル（.gitignore）
├── output/                      # 生成グラフ（.gitignore）
├── src/tileqr_dashboard/
│   ├── adapters/{manual,onedrive}.py
│   ├── sync_pull.py             # 取得 → store再構築
│   ├── ingest.py                # CSV+meta 読み込み・統合
│   ├── metrics.py               # 計算ヘルパ（キャッシュ量・理論式）
│   └── viz/{heatmap,scatter,compare}.py
├── dashboard/
│   ├── app.py                   # Streamlit UI（Webダッシュボード）
│   └── plots.py                 # Plotly図ビルダ
├── run_sync.sh / run_viz.sh / run_dashboard.sh
└── pyproject.toml
```

## セットアップ（WSL2）

```bash
git clone <this-repo>
cd tileQR_dashboard
uv sync          # または: pip install -e .
```

OneDrive を使う場合は `rclone config` で `onedrive:` リモートを設定しておく。

## 使い方

### 1. ソースを定義（`config/sources.toml`）

サーバ1台 = 1ブロック。`type` で取得方法を選ぶ。

```toml
[sources.aoba_b]
type  = "manual"               # NextcloudからDL → inbox/manual/aoba_b に置く
inbox = "inbox/manual/aoba_b"
label = "AOBA-B"
cpu   = "AMD EPYC 7702"        # メタ無しCSVの保険（任意）

[sources.calc]
type   = "onedrive"            # rcloneで自動pull
remote = "onedrive:tileQR_results/calc"
inbox  = "inbox/onedrive/calc"
label  = "calc (研究室サーバ)"
```

### 2. 取り込み

```bash
bash run_sync.sh                # 全ソースをpull → store再構築
bash run_sync.sh --only calc    # calcだけpull
bash run_sync.sh --no-pull      # pullせずinbox再走査のみ
```

AOBA-B は Nextcloud から CSV を DL して `inbox/manual/aoba_b/` に置くだけ。

### 3. 可視化（`output/` に出力）

```bash
bash run_viz.sh all                              # 全部
bash run_viz.sh heatmap --host par001 --threads 128
bash run_viz.sh heatmap --all
bash run_viz.sh scatter                          # メタ(キャッシュ情報)が必要
bash run_viz.sh compare                          # 16:9, 日本語(NotoSansCJK)
```

### 4. Webダッシュボード（研究室機での常時表示向け）

```bash
bash run_dashboard.sh                             # http://localhost:8501
bash run_dashboard.sh --server.address 0.0.0.0    # 大学LAN/Tailscaleに公開
```

Plotly でホバー（nb/ib/GFlops 表示）とズームに対応。3タブ構成。

- 概要：CPU別ピーク性能の比較表
- ホスト詳細：host / threads を選んで nb×ib ヒートマップ
- 分析：キャッシュ量 × 最適nb 散布図（理論曲線つき）

`run_sync.sh` で取り込んだ後、サイドバーの「データ再読み込み」で最新化される。

常時稼働させる場合は、WSL2 の systemd でサービス化するか、Windows の
タスクスケジューラで起動時に立ち上げる。あわせて `run_sync.sh` を
cron / タスクスケジューラで定期実行しておけば、データも自動で新しくなる。
公開はまず localhost のみにして、必要に応じて LAN / Tailscale に広げると安全。

## メタJSON（任意・後付け可）

CSV と同名で隣に置く（`xxx.csv` ↔ `xxx.meta.json`）。CPU比較の散布図や理論式に使う。

```json
{
  "schema_version": 1,
  "host": "par001",
  "label": "AOBA-B",
  "cpu": {
    "model_name": "AMD EPYC 7702 64-Core Processor",
    "sockets": 2, "cores_per_socket": 64, "threads_per_core": 1,
    "numa_nodes": 8, "l1d_per_core_kb": 32, "l2_per_core_kb": 512, "l3_total_mb": 256
  }
}
```

`l2_per_core_kb` / `l3_total_mb` / `sockets` / `cores_per_socket` が揃うと、
コアあたりキャッシュ量と理論式 `nb ≈ √(CacheSize / 32)` を散布図に重ねられる。

> メタJSONを自動採取する `collect_meta.py`（`lscpu --json` をパース）は計測側
> `optuna_tileQR` に置く予定。現状は手書き or 未付与でも動く。

## 新しいサーバを足す

`config/sources.toml` にブロックを1つ足すだけ。とりあえず `manual` にしておけば、
どんなサーバでも「DL → inbox に置く」で取り込める。
