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
│   └── viz/{heatmap,line,scatter,compare}.py
├── dashboard/
│   ├── app.py                   # Streamlit UI（Webダッシュボード）
│   └── plots.py                 # Plotly図ビルダ
├── deploy/tileqr-dashboard.service.example   # 常時稼働(systemd)サンプル
├── run_sync.sh / run_viz.sh / run_dashboard.sh
├── VERSIONING.md / ROADMAP.md
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
bash run_viz.sh heatmap --label AOBA-B --threads 128 --size 8192
bash run_viz.sh heatmap --all
bash run_viz.sh line --threads 64 --size 8192    # nb×GFlops 折れ線（CPU比較）
bash run_viz.sh scatter --threads 64 --size 8192 # メタ(キャッシュ情報)が必要
bash run_viz.sh compare                          # 16:9, 日本語(NotoSansCJK)
```

識別単位は host ではなく CPU(label) / threads / size。同じ組み合わせの
複数 host／試行は (nb, ib) ごとに GFlops を平均してから描画する。
`--threads`/`--size` を省略すると全組み合わせを生成する（`heatmap` は `--all`）。

### 4. Webダッシュボード（研究室機での常時表示向け）

```bash
bash run_dashboard.sh                             # http://localhost:8501
bash run_dashboard.sh --server.address 0.0.0.0    # 大学LAN/Tailscaleに公開
```

Plotly でホバー（nb/ib/GFlops 表示）とズームに対応。4タブ構成。
識別単位は host ではなく CPU(label) / threads / size。同じ組み合わせの
複数 host／試行は (nb, ib) ごとに GFlops を平均してから描画する。

- 概要：(label, threads, size) ごとのピーク性能比較表
- ヒートマップ：CPU(label) / threads / size を選んで nb×ib ヒートマップ
- nb-GFlops曲線：threads / size を選び、CPU(label)別に nb×GFlops を重ねて比較
- 分析：threads / size を選び、キャッシュ量 × 最適nb 散布図（理論曲線つき、点はlabel単位）

`run_sync.sh` で取り込んだ後、サイドバーの「データ再読み込み」で最新化される。

公開はまず localhost のみにして、必要に応じて LAN / Tailscale に広げると安全。
研究室機で立てっぱなしにする手順は下の「常時稼働」節を参照。

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

## 常時稼働（WSL2 systemd）

研究室機を立てっぱなしにして、常にダッシュボードを見られるようにする手順。

### 前提: WSL2 で systemd を有効化

`/etc/wsl.conf` に以下を書いて、`wsl --shutdown` 後に再起動する。

```ini
[boot]
systemd=true
```

### サービス登録

```bash
mkdir -p ~/.config/systemd/user
cp deploy/tileqr-dashboard.service.example ~/.config/systemd/user/tileqr-dashboard.service
# エディタで <USER> とパスを自分の環境に修正
systemctl --user daemon-reload
systemctl --user enable --now tileqr-dashboard
loginctl enable-linger "$USER"        # ログアウト後も動かす
```

`http://localhost:8501` で常時アクセスできる。状態は
`systemctl --user status tileqr-dashboard`、ログは
`journalctl --user -u tileqr-dashboard -f`。

### データの自動更新

`run_sync.sh` を cron で定期実行すると、データも自動で新しくなる。

```bash
# 例: 10分ごとに取り込み（crontab -e で登録）
*/10 * * * * cd ~/Workspace/tileQR_dashboard && .venv/bin/python -m tileqr_dashboard.sync_pull >> /tmp/tileqr_sync.log 2>&1
```

## バージョン管理

セマンティックバージョニングに従う。方針は [VERSIONING.md](VERSIONING.md)、
今後の予定・TODO は [ROADMAP.md](ROADMAP.md) を参照。


## 日本語フォントは直しておくのがおすすめ
「NotoSansCJK 未検出」の警告は環境差ですが、放っておくと compare 表や散布図の日本語ラベルが豆腐（□□□）になるので、研究室機の WSL2 に入れておくといいです。
bashsudo apt update && sudo apt install -y fonts-noto-cjk
rm -rf ~/.cache/matplotlib     # matplotlibのフォントキャッシュをクリア
これで fonts.py が "Noto Sans CJK JP" を拾うようになり、警告も消えて日本語が正しく出ます（研究室デスクトップの WSL2 なら sudo は使えるはずです）。ダッシュボード（Plotly）側はブラウザのフォントで出るので元々問題ないはずですが、PNG出力（run_viz.sh）の方が効いてきます。
