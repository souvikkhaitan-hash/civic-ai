import requests
import time
import threading
from database import save_complaint
from ai_agent import analyze_complaint

REDDIT_URL = "https://www.reddit.com/r/bangalore/new.json?limit=20"
DEFAULT_LAT = 12.9716
DEFAULT_LON = 77.5946

CIVIC_KEYWORDS = [
    "garbage", "flood", "water", "pothole",
    "drain", "sewage", "power", "traffic",
    "road", "streetlight", "accident"
]

PROCESSED = []

def is_civic(text: str) -> bool:
    t = text.lower()
    if len(t) < 15:
        return False
    return any(k in t for k in CIVIC_KEYWORDS)

def fetch():
    try:
        headers = {"User-Agent": "CivicAI/3.0"}
        r = requests.get(REDDIT_URL, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        return r.json()["data"]["children"]
    except Exception as e:
        print("[REDDIT] fetch error:", e)
        return []

def reddit_loop():
    print("[AI] Reddit Agent started (5 mins)")

    while True:
        try:
            posts = fetch()

            for p in posts:
                title = p.get("data", {}).get("title", "").strip()

                if not title or title.lower() in PROCESSED:
                    continue

                PROCESSED.append(title.lower())
                if len(PROCESSED) > 50:
                    PROCESSED.pop(0)

                # civic filter
                if not is_civic(title):
                    continue

                ai = analyze_complaint(title, DEFAULT_LAT, DEFAULT_LON)
                score = ai.get("risk_score", 0)

                # skip ultra low confidence
                if score < 10:
                    continue

                save_complaint(
                    title,
                    ai.get("department"),
                    ai.get("priority"),
                    score,
                    ai.get("explanation"),
                    0,
                    DEFAULT_LAT,
                    DEFAULT_LON,
                    source="reddit"
                )

                print("[REDDIT SAVED]", title[:60])

        except Exception as e:
            print("[REDDIT LOOP ERROR]", e)

        time.sleep(300)

def start_reddit_scheduler():
    t = threading.Thread(target=reddit_loop, daemon=True)
    t.start()