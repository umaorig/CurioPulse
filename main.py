import os
import json
import requests
import feedparser
import random
import time
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from google import genai

# ==========================================
# 1. 環境設定 & 初期化
# ==========================================
load_dotenv()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def load_character_config():
    """SecretsまたはローカルJSONから設定を読み込む"""
    config_json = os.getenv("SETTING_CONFIG")
    if config_json:
        return json.loads(config_json)

    # 読み込み先を setting.json に変更
    config_path = "setting.json"
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # デフォルト設定（ここも汎用的にしておくよ）
    return {
        "bot_name": "Technical Intelligence Bot",
        "youtube_query": "VTuber 3D ライブ MV -shorts",
        "greetings": ["Daily report initialized."],
        "footers": ["End of report."],
        "system_prompt": "3Dライブエンジニアの視点で記事を3行で要約すること。"
    }

config = load_character_config()
client = genai.Client(api_key=GEMINI_API_KEY)
print(client.models.list)
# ==========================================
# 2. 最新モデル動的検知ロジック
# ==========================================
def get_available_flash_models():
    """2026年SDK仕様: supported_actions を使用してFlashモデルを検知"""
    try:
        models = []
        for m in client.models.list():
            # 1. 属性名 supported_actions をチェック
            actions = getattr(m, 'supported_actions', [])

            # 2. 'flash' が名前に含まれ、かつ 'generateContent' が可能なモデルを抽出
            if 'flash' in m.name.lower() and 'generateContent' in actions:
                models.append(m.name)

        # 3. 最新順にソート (models/gemini-2.5-flash -> models/gemini-2.0-flash の順)
        models.sort(reverse=True)

        print(f"📡 2026年最新Flashモデルを検知: {models}")
        return models if models else ['models/gemini-2.5-flash', 'models/gemini-2.0-flash']

    except Exception as e:
        print(f"⚠️ モデルリスト取得失敗、デフォルトを使用します: {e}")
        return ['models/gemini-2.5-flash', 'models/gemini-2.0-flash']

DYNAMIC_MODELS = get_available_flash_models()

def generate_with_fallback(prompt):
    """最新モデルから順にリトライする万能生成関数"""
    for model_name in DYNAMIC_MODELS:
        try:
            print(f"🤖 {model_name} で解析中...")
            response = client.models.generate_content(model=model_name, contents=prompt)
            if response.text:
                return response.text.strip()
        except Exception as e:
            print(f"⚠️ {model_name} エラー: {e}")
            if "429" in str(e): time.sleep(2)
            continue
    return None

# ==========================================
# 3. コンテンツ取得 & AI解析ロジック
# ==========================================
def fetch_summarized_news(urls, count=5):
    """RSSを取得し、AIに要約させ、タイトルと要約を正しく紐付け直す"""
    all_entries = []
    for url in urls:
        feed = feedparser.parse(url)
        if feed.entries: all_entries.extend(feed.entries[:10])
    if not all_entries: return "新しい情報はないみたい。"

    selected = random.sample(all_entries, min(count, len(all_entries)))

    # 1. AIへの指示（自己紹介禁止、フォーマット厳守）
    prompt = f"""
    {config.get('system_prompt')}

    【重要ルール】
    ・自己紹介や前置きは一切不要です。要約のみ出力してください。
    ・各記事の要約は、必ず '###' で区切って出力してください。

    【対象記事】
    """
    for i, entry in enumerate(selected):
        desc = (entry.get('summary', '') or entry.get('description', ''))[:300]
        prompt += f"\n記事{i+1}: {entry.title}\n内容: {desc}\n"

    ai_res = generate_with_fallback(prompt)

    # 2. '###' で分割して、空の要素を削除
    summaries = [s.strip() for s in ai_res.split('###') if s.strip()] if ai_res else []

    # 3. リンクと要約を結合（個別のブロックとして整形）
    formatted_blocks = []
    for i, entry in enumerate(selected):
        # AIの回答が足りない場合は「解析失敗」を入れる
        summary = summaries[i] if i < len(summaries) else "（内容の解析に失敗しちゃった。リンク先を直接確認してね）"

        # 不要な「記事1:」などのゴミが残っていたら消去
        clean_summary = re.sub(r'^記事\d+[:：]\s*', '', summary)

        # 【ここを修正！】 \n を含む処理をf-stringの外で行う
        quoted_summary = clean_summary.replace('\n', '\n> ')

        # 修正後の変数を使う
        block = f"🔹 **[{entry.title}]({entry.link})**\n> {quoted_summary}"
        formatted_blocks.append(block)

    return "\n\n".join(formatted_blocks)

def get_ai_filtered_youtube(count=10):
    """YouTube動画を取得しAIに選別させる"""
    url = "https://www.googleapis.com/youtube/v3/search"
    after = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')

    params = {
        "part": "snippet", "q": config.get("youtube_query"), "type": "video",
        "maxResults": 30, "publishedAfter": after, "regionCode": "JP", "key": YOUTUBE_API_KEY
    }

    try:
        res = requests.get(url, params=params)
        items = res.json().get("items", [])
        if not items: return "目ぼしい動画は見つからなかったよ。"

        candidates = [{"id": i['id']['videoId'], "title": i['snippet']['title']} for i in items]
        titles_text = "\n".join([f"{i+1}. {c['title']}" for i, c in enumerate(candidates)])

        prompt = f"3DライブとMVだけを選んで。番号をコンマ区切りで出力して。\n\n{titles_text}"
        ai_res = generate_with_fallback(prompt)

        indices = [int(n)-1 for n in re.findall(r'\d+', ai_res)] if ai_res else range(count)

        videos = []
        for idx in indices:
            if 0 <= idx < len(candidates):
                c = candidates[idx]
                videos.append(f"🔹 **[{c['title']}](https://www.youtube.com/watch?v={c['id']})**")

        return "\n".join(videos[:count]) if videos else "選別で何も残らなかったよ。"
    except Exception as e:
        return f"YouTube取得エラー: {e}"

# ==========================================
# 4. メイン実行処理
# ==========================================
def main():
    print(f"🚀 オペレーション・ナナ海 起動 (利用可能モデル: {DYNAMIC_MODELS})")

    # 各種情報の取得
    tech_news = fetch_summarized_news(["https://zenn.dev/topics/unity/feed", "https://note.com/hashtag/Unity/rss"], 5)
    live_news = fetch_summarized_news(["https://panora.tokyo/feed"], 3)
    youtube_list = get_ai_filtered_youtube(10)

    # メッセージ構築
    greeting = random.choice(config.get("greetings"))
    footer = random.choice(config.get("footers"))

    contents = [
        f"{greeting}\n\n🛠️ **【Tech & Hack】**\n{tech_news}",
        f"🎤 **【Live & Experience】**\n{live_news}",
        f"🎧 **【Recent Popular 3D/MV】**\n{youtube_list}\n\n{footer}"
    ]

    print("📤 Discordへ送信中...")
    for msg in contents:
        payload = {"username": config.get("bot_name"), "content": msg}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
        time.sleep(1.5)

if __name__ == "__main__":
    main()
