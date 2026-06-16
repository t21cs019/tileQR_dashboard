# ブランチ運用

一人開発だが、変更を安全に積み上げるため `main` / `test` / `dev` の3ブランチで運用する。

## ブランチの役割

| ブランチ | 役割 | 直接コミット |
|---------|------|:----------:|
| `main` | 安定版。動作確認済みのものだけ。リリースタグ（`v0.x.0`）を打つ | しない |
| `test` | 統合・動作確認用。実データ・実環境で検証する場 | 検証時のみ |
| `dev`  | 日常の開発。機能追加・修正はここから | する |

## 基本フロー

```
 dev   ──開発・コミット──►
   │ merge
   ▼
 test  ──実環境で動作確認──►
   │ OKなら merge
   ▼
 main  ──タグ付け（リリース）──►
```

1. `dev` で開発し、こまめにコミット
2. まとまったら `test` にマージし、実環境（AOBA/calc のデータ取り込み、streamlit 起動、グラフ生成）で確認
3. 問題なければ `main` にマージし、バージョンタグを打つ

## 初期セットアップ（最初の一回だけ）

現在 `main` しか無いので、`test` と `dev` を作る。

```bash
git checkout main
git branch test      # main から test を作成
git branch dev       # main から dev を作成
git push -u origin test
git push -u origin dev
git checkout dev     # 普段は dev に居る
```

## 日々の作業

```bash
# --- 開発は dev で ---
git checkout dev
# ...編集...
git add -p
git commit -m "説明"
git push

# --- 検証: dev を test にマージして実環境で確認 ---
git checkout test
git merge --no-ff dev
git push
#   ここで bash run_sync.sh / run_dashboard.sh などを実環境で確認

# --- リリース: test を main にマージしてタグ ---
git checkout main
git merge --no-ff test
git tag -a v0.3.0 -m "リリース内容"
git push origin main --tags

git checkout dev     # 開発に戻る
```

`--no-ff` を付けると「ここでマージした」という履歴が1コミットとして残り、
後から「どの変更がいつ統合されたか」を追いやすい。

## 大きめの機能を作るとき（任意）

機能が大きいときは `dev` からさらに feature ブランチを切ると、
途中の不完全な状態が `dev` を汚さない。

```bash
git checkout dev
git checkout -b feature/collect-meta
# ...開発...
git checkout dev
git merge --no-ff feature/collect-meta
git branch -d feature/collect-meta
```

ブランチ名は `feature/<内容>`、バグ修正なら `fix/<内容>` のように
プレフィックスを付けると整理しやすい。

## バージョンとの対応

- `main` にマージしてリリースするときに、`VERSIONING.md` の方針でタグを打つ
  - 機能追加 → MINOR を上げる（例 `v0.3.0`）
  - バグ修正だけ → PATCH を上げる（例 `v0.2.1`）
- タグは必ず `main` 上のコミットに打つ（安定版の目印にするため）

## 補足: 3本が重いと感じたら

一人開発では `test` の出番が少なく感じることもある。その場合は
`main` + `dev` の2本に減らし、「リリース前の確認は `main` へマージする直前に行う」
形でも十分回る。まずは3本で始めて、面倒なら2本に畳む、くらいの気持ちでよい。