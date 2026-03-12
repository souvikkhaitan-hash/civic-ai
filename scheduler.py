import time
import threading
from internet.weather_agent import run_weather_check
from database import save_complaint, enforce_sla
from ai_agent import analyze_complaint

DEFAULT_LAT = 12.9716
DEFAULT_LON = 77.5946

def ai_loop():
    print("[AI] Weather Scheduler started...")

    while True:
        try:
            print("[WEATHER] Checking weather...")
            weather = run_weather_check()

            if weather and "ai_generated_complaint" in weather:
                ai = weather["ai_generated_complaint"]

                lat = ai.get("latitude") or DEFAULT_LAT
                lon = ai.get("longitude") or DEFAULT_LON
                description = ai.get("description", "Weather-based civic risk")

                ai_res = analyze_complaint(description, lat, lon)

                save_complaint(
                    description,
                    ai_res.get("department"),
                    ai_res.get("priority"),
                    ai_res.get("risk_score"),
                    ai_res.get("explanation"),
                    0,
                    lat,
                    lon,
                    source="weather"
                )
                print("[INFO] Weather complaint saved")

        except Exception as e:
            print(f"[ERR] Weather loop error: {e}")

        time.sleep(60)  # every 1 minute

def sla_loop():
    print("[AI] SLA Monitoring started (Every 1 hour)...")
    while True:
        try:
            print("[SLA] Enforcing SLA rules...")
            enforce_sla()
        except Exception as e:
            print(f"[ERR] SLA loop error: {e}")
        time.sleep(3600)  # Check every 1 hour

def start_scheduler():
    t1 = threading.Thread(target=ai_loop)
    t1.daemon = True
    t1.start()

    t2 = threading.Thread(target=sla_loop)
    t2.daemon = True
    t2.start()