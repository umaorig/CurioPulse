# CurioPulse
### AI-Driven Daily Curiosity & Tech Insight Delivery

このプロジェクトは、毎日の知的好奇心(Curiosity)を刺激する(Pulse)ために設計された、AI情報集約システムです。

## 概要

このプロジェクトは、毎日決まった時間に最新の技術情報や特定のジャンルのコンテンツを収集し、AIによってパーソナライズされた要約レポートを作成します。Google Geminiの最新モデル動的検知機能を備えており、メンテナンスフリーで常に最新のAIモデルを利用できる設計になっています。

## 主な機能

* **RSSニュース集約 & AI要約**: 複数のRSSフィードから記事を取得し、AIが一括で要約を作成します。
* **YouTube AIフィルタリング**: YouTube Data APIで取得した候補から、AIがコンテンツの内容（タイトル）を判断し、目的のジャンルに合致するものだけを選別します。
* **動的モデル検知 (Model Discovery)**: 実行時に利用可能な最新のGemini Flashモデルを自動で検知し、優先的に使用します。
* **マルチモデル・フォールバック**: 最新モデルが利用できない場合やレート制限に達した場合、自動的に下位モデルへリトライします。
* **Discord通知**: 整形されたレポートをDiscord Webhook経由で送信します。
* **JSONによるカスタマイズ**: AIの振る舞いや検索クエリ、メッセージのテンプレートを外部JSONで柔軟に変更可能です。

## セットアップ

### 1. ライブラリのインストール

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下のキーを設定します。

```text
DISCORD_WEBHOOK_URL=your_discord_webhook_url
YOUTUBE_API_KEY=your_youtube_api_key
GEMINI_API_KEY=your_gemini_api_key
SETTING_CONFIG={"bot_name":"..." , ...} # (任意) JSON文字列を直接渡す場合

```

### 3. 設定ファイルの作成

`setting.json`を作成し、Botの振る舞いを定義します（`.env`の`SETTING_CONFIG`が優先されます）。

```json
{
  "bot_name": "Technical Intelligence Bot",
  "youtube_query": "VTuber 3D ライブ MV -shorts",
  "greetings": ["Daily report initialized."],
  "footers": ["End of report."],
  "system_prompt": "3Dライブエンジニアの視点で、以下の技術記事を3行で専門的に要約してください。"
}

```

## 自動実行 (GitHub Actions)

本ツールはGitHub Actionsでの定期実行を想定しています。`.github/workflows/daily_report.yml`を作成し、以下の設定を行うことで毎日自動稼働します。

```yaml
on:
  schedule:
    - cron: '0 22 * * *' # 日本時間 7:00
  workflow_dispatch:

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run script
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          SETTING_CONFIG: ${{ secrets.SETTING_CONFIG }}
        run: python main.py

```
