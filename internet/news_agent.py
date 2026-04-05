import requests
import os
from dotenv import load_dotenv
from ai_agent import analyze_complaint
from database import save_complaint, get_active_location

# 🔥 ENV
load_dotenv()
API_KEY = os.getenv("NEWS_API_KEY")

# =========================
# 📍 LOCATION OVERRIDE
# =========================
STATE_MAP = {
    "Bengaluru": "Karnataka",
    "Kolkata": "West Bengal",
    "Delhi": "Delhi",
    "Mumbai": "Maharashtra"
}

# ==============================
# 🧠 REAL CIVIC FILTER (STRICT)
# ==============================
def is_real_civic_issue(text):
    text = text.lower()
    infra = ["road", "bridge", "drain", "sewage", "garbage", "flood", "waterlogging", "power outage", "pothole", "overflow"]
    civic_context = ["collapsed", "blocked", "overflow", "failure", "complaints", "residents suffer", "bbmp", "municipal", "civic body"]
    return any(k in text for k in infra) and any(k in text for k in civic_context)


# ==============================
# 📰 FETCH + INGEST NEWS
# ==============================
def fetch_and_ingest_news():
    if not API_KEY:
        print("[NEWS] Missing API key")
        return

    try:
        # Step 1: Force system location even for news search
        loc = get_active_location()
        city = loc.get("city", "Bengaluru")
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        
        state = STATE_MAP.get(city, "Karnataka")
        area = city
        
        KEYWORDS = "flood OR garbage OR road OR water OR electricity OR traffic OR pothole"

        url = (
            f"https://newsapi.org/v2/everything"
            f"?q={city} AND ({KEYWORDS})"
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

        for article in articles[:10]:
            title = article.get("title", "")
            desc = article.get("description", "")
            full_text = f"{title}. {desc}".strip()

            if not title or len(title) < 10:
                continue

            # 🚫 Strict civic filter
            if not is_real_civic_issue(full_text): continue

            print(f"[AI LOCATION OVERRIDE] {state} {city} {area}")

            # 🤖 AI analysis
            ai = analyze_complaint(full_text, lat=lat, lon=lon)
            risk = ai.get("risk_score", 0)

            if risk < 25: continue

            # 💾 Save to DB (real ingestion)
            save_complaint(
                title,
                ai.get("department"),
                ai.get("priority"),
                risk,
                str(ai.get("explanation")),
                user_id=None,
                lat=lat,
                lon=lon,
                manual_location=city,
                image_path=None,
                address=None,
                state=state,
                city=city,
                area=area,
                source="ai"
            )

            print(f"[NEWS ACCEPTED] {title[:60]} | Score: {risk}")
            accepted += 1

        print(f"[NEWS] Synced {accepted} reports with {city} jurisdiction")

    except Exception as e:
        print("[NEWS ERROR]", str(e))


# ==============================
# 🔁 SCHEDULER LOOP
# ==============================
def news_loop():
    print("[AI] News Civic Inspector started...")
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