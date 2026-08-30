# ロードマップ / TODO

tileQR_dashboard の今後の機能追加・改善のメモ。`[x]` は実装済み。

## 計測側との連携（optuna_tileQR）
- [ ] `collect_meta.py`: `lscpu --json` から `<csv名>.meta.json` を自動生成
- [ ] `sync_push.sh`: calc 等から OneDrive へ rclone で自動push
- [ ] チューニング結果（Optuna が見つけた最適 nb/ib）をダッシュボードに表示

## 可視化
- [x] nb×ib ヒートマップ
- [x] nb×GFlops 折れ線（(label, threads, size) の組を複数選択して比較・ピークにMax注釈）
- [x] 散布図：nb × スレッドあたりキャッシュ量（理論帯 25〜75%・50%ライン・AOBA強調）
- [x] CPU比較表（16:9, 日本語）
- [x] 複数 size 対応（識別単位を host → (label, threads, size) に変更、host横断で平均集約）
- [x] ダッシュボードから図を PNG エクスポート
- [ ] 図・表の CSV エクスポート
- [ ] データに含めるホスト/CSV の選択
- [ ] スレッドスケーリングのビュー（64 vs 128 の並列効率）
- [ ] ピーク近傍 top-N パラメータの一覧

## データ・品質
- [ ] pytest による単体テスト（ingest / metrics / plots）
- [ ] メタJSON のスキーマ検証（jsonschema）
- [ ] CSV 取り込み時のバリデーション（列・型・異常値）
- [ ] 取り込み済みファイルの来歴管理（ハッシュで重複検出）

## インフラ・運用
- [ ] GitHub Actions で lint + test（CI）
- [x] GitHub Actions で Docker イメージを GHCR に公開（`.github/workflows/docker-publish.yml`）
- [x] ZimaOS / Docker Compose 対応（dashboard + receiver, 名前付きボリューム, `x-casaos`）
- [ ] LICENSE 追加（MIT など）
- [x] WSL2 常時稼働（systemd）のサンプル → `deploy/`
- [ ] `run_sync.sh` の定期実行（cron / タスクスケジューラ）
- [ ] README にダッシュボードのスクリーンショット

## データ源・受け取り・計測プラン連携
- [x] tileQR_data を主データ源に（derived parquet + machines.yaml を HTTPS取得、config単位のlabel）
- [x] 起動時自動取得＋サイドバー「tileQR_data から更新」ボタン（`datarepo.py` / `sync_data.py`）
- [x] ssrfb を tileqr グラフから分離（`kind` タグ）／データ源フィルタ（`origin`）
- [x] 受信API（`receiver.py`）: 計測機からのCSV/メタHTTPアップロード → 自動 store 再構築（補助）
- [x] ブラウザからのCSV手動アップロード（サイドバー・補助）
- [x] 計測プラン（plasma-bench の `PROGRESS.md`）の閲覧・編集タブ（往復同期）
- [x] plasma-bench 側 `sync_results.sh http` / `sync_plan.sh`（push/pull）

## 研究テーマ寄り（将来）
- [ ] perf によるキャッシュヒット率計測との連携
- [ ] Amplify ベースのチューニング手法の取り込み
- [ ] アーキテクチャ（キャッシュ階層・NUMA）と最適nbの関係分析の自動化

---

## 優先度メモ（クロードの提案）

正式版 `1.0.0` に向けて、いま効果が大きい順に:

1. **`collect_meta.py`（計測側）** — 散布図とCPU比較が自動で埋まり、ダッシュボードの
   価値が一段上がる。実装の手間も小さく費用対効果が高い。
2. **pytest + CI** — 「修正しながら育てる」段階なので、壊れていないことを自動で
   担保できると安心。公開リポジトリの体裁としても効く。
3. **データに含めるホスト/CSV の選択** — `aggregate_runs` に `hosts` 引数を
   入れてあるので、サイドバーにマルチセレクトを足すだけ。外れ値の計測を除外できる。
4. **LICENSE 追加** — 就活でも見せる公開リポジトリなので、早めに入れると体裁が整う。

逆に急がなくてよいもの: スレッドスケーリングビュー・top-N 表示・CSV エクスポートは
「あると便利」だが、上の基盤が整ってからで十分。

---

## バージョン履歴（概要）
v0.1.0 初版 → v0.2.0 折れ線 → v0.3.0 CPUプリセット →
v0.4.0 複数size対応 → v0.5.0 折れ線の複数選択・散布図の軸変更・PNGエクスポート →
v0.6.0 CPUプリセット拡充・calc運用変更 →
v0.7.0 ZimaOS/Docker Compose対応・受信API（HTTP/手動アップロード）・計測プラン編集タブ（往復同期）→
v0.7.1 ssrfb を tileqr グラフから分離（kind タグ）→
v0.8.0 tileQR_data を主データ源に（derived parquet 取得・config単位のlabel・起動時自動＋更新ボタン）