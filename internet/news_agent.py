import requests
import os
from dotenv import load_dotenv
from ai_agent import analyze_complaint
from database import save_complaint

# 🔥 ENV
load_dotenv()
API_KEY = os.getenv("NEWS_API_KEY")

CITY = "Bangalore"
DEFAULT_LAT = 12.9716
DEFAULT_LON = 77.5946

# ==============================
# 🧠 REAL CIVIC FILTER (STRICT)
# ==============================
def is_real_civic_issue(text):
    text = text.lower()

    # Infrastructure signals
    infra = [
        "road", "bridge", "drain", "sewage", "garbage",
        "flood", "waterlogging", "power outage",
        "streetlight", "pothole", "overflow"
    ]

    # Municipal responsibility context
    civic_context = [
        "collapsed", "blocked", "overflow",
        "failure", "complaints", "residents suffer",
        "bbmp", "municipal", "civic body"
    ]

    has_infra = any(k in text for k in infra)
    has_context = any(k in text for k in civic_context)

    return has_infra and has_context


# ==============================
# 📰 FETCH + INGEST NEWS
# ==============================
def fetch_and_ingest_news():
    if not API_KEY:
        print("[NEWS] Missing API key")
        return

    try:
        KEYWORDS = "flood OR garbage OR road OR water OR electricity OR traffic OR pothole"

        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={CITY} AND ({KEYWORDS})"
            f"&sortBy=publishedAt"
            f"&language=en"
            f"&apiKey={API_KEY}"
        )

        response = requests.get(url, timeout=10)
        data = response.json()

        if data.get("status") != "ok":
            print("[NEWS] API error:", data.get("message"))
            return

        articles = data.get("articles", [])
        accepted = 0

        for article in articles[:15]:
            title = article.get("title", "")
            desc = article.get("description", "")
            full_text = f"{title}. {desc}".strip()

            if not title or len(title) < 10:
                continue

            # 🚫 Strict civic filter
            if not is_real_civic_issue(full_text):
                print("[NEWS FILTERED]", title[:60])
                continue

            # 🤖 AI analysis
            ai = analyze_complaint(full_text, lat=DEFAULT_LAT, lon=DEFAULT_LON)
            risk = ai.get("risk_score", 0)

            # 🚫 Minimum threshold
            if risk < 25:
                print("[NEWS LOW SCORE]", title[:60])
                continue

            # 💾 Save to DB (real ingestion)
            save_complaint(
                title,
                ai.get("department"),
                ai.get("priority"),
                risk,
                ai.get("explanation"),
                0,  # system user
                DEFAULT_LAT,
                DEFAULT_LON,
                source="news"
            )

            print(f"[NEWS ACCEPTED] {title[:70]} | Score: {risk}")
            accepted += 1

        print(f"[NEWS] Accepted {accepted} civic reports")

    except Exception as e:
        print("[NEWS ERROR]", str(e))


# ==============================
# 🔁 SCHEDULER LOOP
# ==============================
def news_loop():
    print("[AI] News Civic Ingestion Agent started (Every 10 mins)...")
    import time
    while True:
        fetch_and_ingest_news()
        time.sleep(600)  # 10 mins


# ==============================
# 🚀 STARTER
# ==============================
def start_news_scheduler():
    import threading
    t = threading.Thread(target=news_loop, daemon=True)
    t.start()