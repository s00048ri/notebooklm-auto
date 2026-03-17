# YouTubeの動画リストからNotebookLMノートブックを自動作成するツールを作った

## はじめに

Google NotebookLMは、YouTube動画を含むさまざまなソースをもとにAIが要約や質問応答をしてくれる便利なツールです。しかし、複数の動画を一つずつ手動でNotebookLMに登録していく作業は、数が多くなると非常に面倒です。

そこで、**YouTube URLのリストを渡すだけで、自動的にNotebookLMにノートブックを作成し、要約と共有リンクを一括生成するツール**「NotebookLM Auto」を作りました。

### こんな人に便利

- カンファレンスの録画動画を大量にNotebookLMに登録して整理したい
- 複数のYouTube動画をまとめて要約・比較したい
- チームメンバーに共有リンク付きで要約一覧を配布したい

---

## 何ができるのか

1. **YouTube URLのリストを入力**（テキスト、CSV、Web UIからのドラッグ&ドロップ）
2. **各動画に対してNotebookLMノートブックを自動作成**（動画タイトルを自動取得してノートブック名に設定）
3. **AIが要約を自動生成**（日本語・英語・カスタムプロンプト対応）
4. **共有リンクを自動取得**
5. **結果をCSV/JSON/Markdownで出力**（Google Spreadsheetに貼り付け可能）

CLIとWeb UIの両方に対応しています。

### Web UIのイメージ

Web UIでは、URLを入力して「実行する」ボタンを押すだけ。リアルタイムで処理の進捗が表示され、完了後はCSVエクスポートやクリップボードコピーが可能です。

---

## セットアップ手順

### 前提条件

- **Python 3.10以上**がインストールされていること
- **Googleアカウント**（NotebookLMにアクセスできるもの）

> Pythonのインストールがまだの場合は、[python.org](https://www.python.org/downloads/) からダウンロードしてください。macOSの場合は `brew install python` でもOKです。

### 1. リポジトリをクローン

ターミナル（macOS）またはコマンドプロンプト/PowerShell（Windows）を開いて、以下のコマンドを実行します。

```bash
git clone https://github.com/s00048ri/notebooklm-auto.git
cd notebooklm-auto
```

### 2. Python仮想環境を作成

プロジェクト専用のPython環境を作ります。他のプロジェクトとライブラリの衝突を防ぐためです。

```bash
# 仮想環境を作成
python3 -m venv .venv

# 仮想環境を有効化
source .venv/bin/activate    # macOS / Linux
# .venv\Scripts\activate     # Windows の場合
```

> ターミナルのプロンプトに `(.venv)` と表示されれば成功です。

### 3. 依存パッケージをインストール

```bash
# 本体をインストール
pip install -e "."

# Web UIを使う場合はFlaskも追加
pip install flask

# ブラウザ自動操作用のChromiumをインストール
playwright install chromium
```

### 4. NotebookLMへのログイン

初回のみ、Googleアカウントでの認証が必要です。

```bash
notebooklm login
```

ブラウザが自動で開くので、NotebookLMで使いたいGoogleアカウントでログインしてください。ログイン情報はローカルに安全に保存されます。

> ⚠️ セッションが切れた場合（数日〜数週間後）は、再度このコマンドでログインし直してください。

---

## 使い方

### 方法1: Web UI（おすすめ）

```bash
python -m notebooklm_auto.web
```

ブラウザで `http://localhost:5000` にアクセスすると、直感的なUIが表示されます。

**操作手順：**
1. テキストエリアにYouTube URLを1行ずつ入力（またはCSVファイルをドラッグ&ドロップ）
2. 要約の言語を選択（日本語 / English / カスタムプロンプト）
3. 「実行する」をクリック
4. リアルタイムで進捗を確認
5. 完了後、「CSV出力」または「クリップボードにコピー」で結果を取得

### 方法2: コマンドライン（CLI）

```bash
# テキストファイルから実行
notebooklm-auto --file urls.txt

# CSVファイルから実行（タイトル列があればノートブック名に使用）
notebooklm-auto --file sessions.csv

# URLを直接指定
notebooklm-auto --urls https://youtube.com/watch?v=xxx https://youtube.com/watch?v=yyy

# 英語で要約を生成
notebooklm-auto --file urls.txt --prompt "Summarize the key points in English"

# CSV形式で出力
notebooklm-auto --file urls.txt --output-format csv
```

---

## 入力ファイルの形式

### テキストファイル（urls.txt）

1行に1つのYouTube URLを記載するだけです。

```
https://youtube.com/watch?v=xxxxx
https://youtube.com/watch?v=yyyyy
https://youtube.com/live/zzzzz
```

### CSVファイル（sessions.csv）

タイトル列があれば、自動的にNotebookLMのノートブック名に使用されます。

```csv
Session Title,YouTube URL
AIの未来について,https://youtube.com/watch?v=xxxxx
機械学習入門,https://youtube.com/watch?v=yyyyy
```

> タイトル列がない場合やテキストファイルの場合は、YouTube動画のタイトルを自動取得してノートブック名に設定します。

---

## 設定のカスタマイズ

プロジェクト直下の `config.yaml` で設定を変更できます。

```yaml
# 要約プロンプト（--prompt フラグで上書き可能）
summary_prompt: "この動画の要点を日本語で要約してください"

# 同時処理数（NotebookLMの負荷軽減のため低めに設定）
max_concurrent: 2

# 出力形式: json / csv / markdown
output_format: csv

# 出力ディレクトリ
output_dir: ./output
```

---

## 出力例

### CSVの出力例

| # | タイトル | URL | ステータス | 要約 | 共有リンク | 時間(秒) |
|---|---------|-----|-----------|------|-----------|---------|
| 1 | AIの未来について | https://youtube.com/... | 成功 | この動画では、AI技術の... | https://notebooklm.google.com/... | 21.7 |
| 2 | 機械学習入門 | https://youtube.com/... | 成功 | 機械学習の基礎について... | https://notebooklm.google.com/... | 17.6 |

出力されたCSVはそのままGoogle Spreadsheetに貼り付けることができます。

---

## よくある質問

### Q: NotebookLMのAPIを使っていますか？

A: いいえ。NotebookLMには現時点で公式APIが存在しません。本ツールは [`notebooklm-py`](https://github.com/nichochar/notebooklm-py) ライブラリを使い、Playwrightによるブラウザ自動操作でNotebookLMのWeb UIを操作しています。

### Q: 無料で使えますか？

A: はい。NotebookLM自体がGoogleアカウントがあれば無料で使えるため、本ツールも完全無料です。APIキーやサブスクリプションは不要です。

### Q: セッションが切れた場合は？

A: `notebooklm login` を再実行してGoogleアカウントでログインし直してください。

### Q: 同時処理数を上げてもいいですか？

A: `max_concurrent` を3〜4程度までなら問題ありませんが、上げすぎるとNotebookLM側のレート制限に引っかかる可能性があります。デフォルトの2が安定的です。

### Q: YouTube以外のソースにも対応していますか？

A: 現在はYouTube URLのみに対応しています。NotebookLMはWebページやPDFなど他のソースにも対応しているため、将来的に拡張する可能性があります。

---

## 技術的な仕組み

内部的には以下の流れで動作しています：

1. YouTube URLリストを読み込み
2. 各URLに対して：
   - YouTube oEmbed APIで動画タイトルを取得（APIキー不要）
   - Playwrightで自動化されたブラウザ上でNotebookLMにアクセス
   - ノートブックを作成し、YouTubeソースを追加
   - プロンプトに基づいてAIに要約を生成させる
   - 共有リンクを取得
3. 結果をCSV/JSON/Markdownで出力

Web UIはFlaskで構成され、Server-Sent Events (SSE) を使ってリアルタイムの進捗表示を実現しています。

### 使用技術

| 技術 | 用途 |
|------|------|
| Python 3.10+ | ランタイム |
| notebooklm-py | NotebookLM操作ライブラリ |
| Playwright | ブラウザ自動操作 |
| Flask | Web UIサーバー |
| SSE (Server-Sent Events) | リアルタイム進捗通知 |
| Rich | CLI出力の装飾 |
| YouTube oEmbed API | 動画タイトル取得 |

---

## GitHub

ソースコードはGitHubで公開しています。スター、Issue、PRはお気軽にどうぞ！

👉 **https://github.com/s00048ri/notebooklm-auto**

---

## おわりに

NotebookLMは動画を後から見返したり、深掘りしたりするのに非常に便利なツールです。しかし、カンファレンスの録画動画など大量のコンテンツを一つずつ登録するのは大変です。

このツールを使えば、CSVファイル一つで数十本の動画をまとめてNotebookLMに登録でき、要約と共有リンクも自動で取得できます。

ぜひ試してみてください！フィードバックやご要望があれば、GitHubのIssueまたはこのNoteのコメント欄でお知らせください。
