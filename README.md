# NotebookLM Auto

YouTubeのURLリストからNotebookLMノートブックを自動作成し、要約と共有リンクを一括生成するツールです。

> **Automatically create NotebookLM notebooks from YouTube URLs, generate summaries, and get shareable links — all in batch.**

## Features

- YouTube URLのリストを入力するだけで、NotebookLMノートブックを自動作成
- 動画タイトルを自動取得してノートブック名に設定
- 要約を自動生成（日本語・英語・カスタムプロンプト対応）
- 共有リンクを自動取得
- CSV/JSON/Markdown形式で結果を出力
- Web UI（リアルタイム進捗表示付き）とCLIの両方に対応
- CSV/TXTファイルからの一括読み込み

## Demo

### Web UI

```
python -m notebooklm_auto.web
```

ブラウザで `http://localhost:5000` にアクセスすると、以下の操作ができます：

- YouTube URLの入力（1行1URL、またはCSVファイルのアップロード）
- 要約言語の選択（日本語/英語/カスタム）
- リアルタイムの処理進捗表示
- 結果のCSVエクスポート・クリップボードコピー

### CLI

```bash
# URLリストファイルから実行
notebooklm-auto --file urls.csv

# URLを直接指定
notebooklm-auto --urls https://youtube.com/watch?v=xxx https://youtube.com/watch?v=yyy

# 英語で要約
notebooklm-auto --file urls.csv --prompt "Summarize the key points in English"

# 出力形式を指定
notebooklm-auto --file urls.csv --output-format csv
```

## Setup

### 1. 前提条件

- Python 3.10以上
- Google アカウント（NotebookLMにアクセスできるもの）

### 2. インストール

```bash
git clone https://github.com/YOUR_USERNAME/notebooklm-auto.git
cd notebooklm-auto

# 仮想環境を作成
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 依存関係をインストール
pip install -e "."

# Flaskもインストール（Web UIを使う場合）
pip install flask

# Playwrightのブラウザをインストール
playwright install chromium
```

### 3. NotebookLMへのログイン

初回のみ、以下のコマンドでGoogleアカウントにログインします：

```bash
notebooklm login
```

ブラウザが開くので、Googleアカウントでログインしてください。セッション情報がローカルに保存されます。

### 4. 入力ファイルの準備

#### テキストファイル（urls.txt）

```
https://youtube.com/watch?v=xxxxx
https://youtube.com/watch?v=yyyyy
```

#### CSVファイル（urls.csv）

```csv
Session Title,YouTube URL
セッション名1,https://youtube.com/watch?v=xxxxx
セッション名2,https://youtube.com/watch?v=yyyyy
```

CSVの場合、`Session Title` / `Title` / `Name` 列があればノートブック名に使用します。
列がない場合はYouTube動画のタイトルを自動取得します。

### 5. 実行

```bash
# CLI
notebooklm-auto --file input/urls.csv --output-format csv

# Web UI
python -m notebooklm_auto.web
```

## Configuration

`config.yaml` で設定をカスタマイズできます：

```yaml
# 要約プロンプト
summary_prompt: "この動画の要点を日本語で要約してください"

# 同時処理数（NotebookLMのレート制限回避のため低めに設定）
max_concurrent: 2

# 出力形式: json / csv / markdown
output_format: csv

# 出力ディレクトリ
output_dir: ./output
```

## Project Structure

```
notebooklm-auto/
├── src/notebooklm_auto/
│   ├── __init__.py
│   ├── __main__.py        # python -m エントリポイント
│   ├── main.py            # CLIエントリポイント
│   ├── web.py             # Web UIサーバー（Flask + SSE）
│   ├── config.py          # 設定管理
│   ├── input_parser.py    # URL入力パーサー（CSV/TXT対応）
│   ├── processor.py       # NotebookLM操作コア
│   ├── output_writer.py   # 結果出力（JSON/CSV/Markdown）
│   ├── models.py          # データモデル
│   ├── templates/
│   │   └── index.html     # Web UIテンプレート
│   └── static/            # 静的ファイル
├── config.yaml            # デフォルト設定
├── pyproject.toml
└── README.md
```

## How It Works

1. YouTube URLリストを読み込み
2. 各URLに対して：
   - YouTube oEmbed APIで動画タイトルを取得
   - NotebookLMにノートブックを作成
   - YouTubeソースを追加
   - プロンプトに基づいて要約を生成
   - 共有リンクを取得
3. 結果をCSV/JSON/Markdownで出力

内部では [`notebooklm-py`](https://github.com/nichochar/notebooklm-py) ライブラリを使用し、Playwrightでブラウザ自動操作を行っています。

## Notes

- NotebookLMにはAPIが公開されていないため、ブラウザ自動操作で動作します
- セッションが切れた場合は `notebooklm login` で再ログインしてください
- 同時処理数を上げすぎるとレート制限に引っかかる可能性があります（推奨: 2〜3）

## License

MIT
