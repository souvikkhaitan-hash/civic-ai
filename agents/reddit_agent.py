import requests
import time
import threading
from database import save_complaint, get_active_location
from ai_agent import analyze_complaint

REDDIT_URL = "https://www.reddit.com/r/india/new.json?limit=20" # broader scope for localized filtering

# =========================
# 📍 LOCATION OVERRIDE
# =========================
STATE_MAP = {
    "Bengaluru": "Karnataka",
    "Kolkata": "West Bengal",
    "Delhi": "Delhi",
    "Mumbai": "Maharashtra"
}

CIVIC_KEYWORDS = [
    "garbage", "flood", "water", "pothole",
    "drain", "sewage", "power", "traffic",
    "road", "streetlight", "accident"
]

PROCESSED = []

def is_civic(text: str) -> bool:
    t = text.lower()
    if len(t) < 15: return False
    return any(k in t for k in CIVIC_KEYWORDS)

def fetch():
    try:
        headers = {"User-Agent": "CivicAI/3.0"}
        r = requests.get(REDDIT_URL, headers=headers, timeout=10)
        if r.status_code != 200: return []
        return r.json()["data"]["children"]
    except Exception as e:
        print("[REDDIT] fetch error:", e)
        return []

def reddit_loop():
    print("[AI] Reddit Community Inspector started...")

    while True:
        try:
            # 🛑 Step 0: Get active jurisdiction
            loc = get_active_location()
            city = loc.get("city", "Bengaluru")
            lat = loc.get("latitude")
            lon = loc.get("longitude")
            
            state = STATE_MAP.get(city, "Karnataka")
            area = city
            
            # Step 1: Use more broad subreddit if needed, but filter by active city context later
            # (Keeping bangalore for now but we will override location)
            posts = fetch()

            for p in posts:
                title = p.get("data", {}).get("title", "").strip()

                if not title or title.lower() in PROCESSED: continue
                PROCESSED.append(title.lower())
                if len(PROCESSED) > 50: PROCESSED.pop(0)

                # Step 2: Strictly civic detection
                if not is_civic(title): continue
                
                # 🛑 FORCE SYSTEM ACTIVE LOCATION 🛑
                print(f"[AI LOCATION OVERRIDE] {state} {city} {area}")

                # Step 3: AI analysis with active coordinates
                ai = analyze_complaint(title, lat, lon)
                score = ai.get("risk_score", 0)

                if score < 10: continue

                # Step 4: Final save to Panchayat jurisdiction
                save_complaint(
                    title,
                    ai.get("department"),
                    ai.get("priority"),
                    score,
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

                print(f"[REDDIT ACCEPTED] {title[:60]}")

        except Exception as e:
            print("[REDDIT LOOP ERROR]", e)

        time.sleep(300)

def start_reddit_scheduler():
    t = threading.Thread(target=reddit_loop, daemon=True)
    t.start()