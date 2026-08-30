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
├── plan/<key>/PROGRESS.md       # 計測プラン（受信・編集。.gitignore）
├── data_repo/                   # tileQR_data から取得したキャッシュ（.gitignore）
├── src/tileqr_dashboard/
│   ├── adapters/{manual,onedrive}.py
│   ├── datarepo.py              # tileQR_data 取得＋derived→統合テーブル整形（主データ源）
│   ├── sync_data.py             # tileQR_data 取得 → store再構築（起動時/更新ボタン/cron）
│   ├── sync_pull.py             # inbox（補助）取得 → store再構築
│   ├── ingest.py                # CSV+meta 読み込み・統合（datarepo と inbox を合成）
│   ├── metrics.py               # 計算ヘルパ（キャッシュ量・理論式）
│   ├── receiver.py              # 受信API（HTTPアップロード・プラン往復同期）
│   ├── plan.py                  # PROGRESS.md の読み書き（plasma-bench と互換）
│   └── viz/{heatmap,line,scatter,compare}.py
├── dashboard/
│   ├── app.py                   # Streamlit UI（Webダッシュボード + 計測プラン編集）
│   └── plots.py                 # Plotly図ビルダ
├── docker-compose.yml           # ZimaOS/Docker（dashboard + receiver）
├── docker/entrypoint.sh         # 初回起動時の config seed・tileQR_data 取得
├── .github/workflows/docker-publish.yml  # GHCR へイメージ公開
├── deploy/tileqr-dashboard.service.example   # 常時稼働(systemd)サンプル
├── run_sync_data.sh / run_sync.sh / run_viz.sh / run_dashboard.sh / run_receiver.sh
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
type  = "manual"               # 研究室サーバ（手動運用）
inbox = "inbox/manual/calc"
label = "calc (研究室サーバ)"
cpu   = "xeon_silver_4214"     # cpus.toml のプリセットキーを指定可

# type = "onedrive" にすると rclone 経由で自動pullも可能
# remote = "onedrive:tileQR_results/<key>"
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
- nb-GFlops曲線：(CPU・threads・size) の組み合わせを複数選んで nb×GFlops を重ねて比較
  （各系列のピークに Max XXX @ nb=YYY を注釈）
- 分析：threads / size を選び、nb × スレッドあたりキャッシュ量 散布図
  （25〜75%帯+50%ライン、点は(label,threads,size)単位、AOBAは別色・別マーカー）

`run_sync.sh` で取り込んだ後、サイドバーの「データ再読み込み」で最新化される。

公開はまず localhost のみにして、必要に応じて LAN / Tailscale に広げると安全。
研究室機で立てっぱなしにする手順は下の「常時稼働」節を参照。

## Docker / ZimaOS で動かす

ZimaOS（や普通の Docker 環境）では **docker compose** で2サービスを同時に立ち上げる:

| サービス | ポート | 役割 |
|---|---|---|
| `dashboard` | 8501 | Streamlit ダッシュボード（閲覧・計測プラン編集） |
| `receiver`  | 8502 | 受信API（計測機からのCSVアップロード・プラン往復同期） |

データ（`config` / `inbox` / `store` / `output` / `plan`）は名前付きボリュームで
永続化し、両サービスで共有する（receiver が inbox に書く → store 再構築 → dashboard が読む）。

```bash
# GHCR のビルド済みイメージを使う（既定）
docker compose up -d
#   http://<host>:8501  ダッシュボード
#   http://<host>:8502  受信API（/health で死活確認）

# リポジトリからローカルビルドする場合は docker-compose.yml の `build: .` を有効化して
docker compose up -d --build
```

イメージは `main`／タグ push で GitHub Actions が **GHCR**（`ghcr.io/t21cs019/tileqr_dashboard`）
に自動公開する。**ZimaOS** では「独自アプリをインストール」からこの `docker-compose.yml`
を取り込めば、`x-casaos:` メタデータ（タイトル・アイコン・ポート）付きで入る。

- 設定（`sources.toml` / `cpus.toml`）は初回起動時に既定値が config ボリュームへ seed される。
  ソースを足すときは config ボリューム内の `sources.toml` を編集して receiver を再起動。
- 受信APIに認証をかけるなら `.env` に `DASHBOARD_TOKEN` を設定（`.env.example` 参照）。

## データ源: tileQR_data（主）

計測データは GitHub リポジトリ **[`tileQR_data`](https://github.com/t21cs019/tileQR_data)**
で一元管理する。ダッシュボードはそこの**組み立て済み derived データ**を主データ源として読む。

- 取得するのは `derived/qr_sweep.parquet`（tileqr）・`derived/ssrfb.parquet`・`machines.yaml`
  の3ファイルだけ（git 不要・HTTPS で数MB）。`machines.yaml` の
  `architectures` / `configs` / `nodes` から CPU 諸元・キャッシュを補完する。
- **識別単位(label)は `config`**（例 `aoba-b_s2_smt-off`）。sockets 数・SMT の違いを
  別系列として区別する（`node` は host として平均集約）。CPU モデル名は別列で表示。
- 取得タイミング: **コンテナ起動時に自動取得**（dashboard サービス）＋サイドバーの
  **「tileQR_data から更新」**ボタンでいつでも再取得。

```bash
# ローカル/手動で取得し直す
bash run_sync_data.sh
# 取得元を別ブランチ/フォークに変える場合
TILEQR_DATA_BASE=https://raw.githubusercontent.com/<owner>/<repo>/<ref> bash run_sync_data.sh
```

inbox（下記の受信API・手動アップロード）は**補助**扱いで、tileQR_data と合わせて表示できる
（サイドバーの「データ源」で `tileQR_data` / `inbox` を切り替え可能。`origin` 列で区別）。

## データ受け取りの自動化（受信API・補助）

tileQR_data に載せる前の一時的な確認用に、計測機（**plasma-bench**）から結果を
**手動**または **HTTP** で直接入れることもできる（補助経路）:

- **手動アップロード**: ダッシュボード左サイドバーの「CSV手動アップロード」から、
  取り込み先ソースを選んで CSV / `*.meta.json` を投入 → その場で store 再構築。
- **HTTP 自動受信**: 計測機の `scripts/sync_results.sh http` が受信APIへ POST する。
  着地後に store が自動再構築され、ダッシュボードは parquet の更新を検知して最新化する。

```bash
# 計測機側（plasma-bench リポジトリ）
HTTP_URL=http://zima:8502 HTTP_KEY=calc bash scripts/sync_results.sh http
#   HTTP_KEY は sources.toml のソースキー。DASHBOARD_TOKEN を設定していれば
#   HTTP_TOKEN=<token> も付ける。
```

受信APIの主なエンドポイント: `POST /upload/<key>`（CSV/メタ）、`GET|POST /plan/<key>`
（計測プラン）、`GET /health`、`GET /sources`。

## 計測プランの閲覧・編集（往復同期）

計測機側の「計測の自動化機能」（plasma-bench の `plan`）が管理する `PROGRESS.md`
（ssrfb / tileqr / tuning の3表）を、ダッシュボードの **「計測プラン」タブ**で
閲覧・編集できる。

1. 計測機で `bash scripts/sync_plan.sh push` → `PROGRESS.md` をダッシュボードへ送る
2. ダッシュボードの「計測プラン」タブで、ソースを選んで表を編集
   （行追加・`note`/`skip`・スイープ範囲など。`status`/`coverage` は計測機が自動更新する
   読み取り専用列）→「保存」
3. 計測機で `bash scripts/sync_plan.sh pull` → 編集版を取り戻す
4. 計測機で `plan scan`（status/coverage 再計算）→ `plan run`（未計測分を実行）

フォーマットは plasma-bench 側 `plan/manifest.py` と互換（桁揃えまで一致）なので、
どちら側で編集しても壊れない。

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
    "numa_nodes": 8, "l1d_per_core_kb": 32, "l2_per_core_kb": 512, "l3_per_socket_mb": 256
  }
}
```

> `l3_per_socket_mb` は1ソケットあたりのL3容量（旧キー名 `l3_total_mb` のままでも後方互換で読める）。

`l2_per_core_kb` / `l3_per_socket_mb` / `sockets` / `cores_per_socket` が揃うと、
スレッドあたりキャッシュ量と理論式 `nb ≈ √(CacheSize/thread × ratio / 32)` を
散布図（横軸nb・縦軸キャッシュ/スレッド、25〜75%帯+50%ライン）に重ねられる。

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
