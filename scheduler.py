import time
import threading
from internet.weather_agent import run_weather_check
from database import save_complaint, enforce_sla, get_active_location
from ai_agent import analyze_complaint

# =========================
# 📍 LOCATION OVERRIDE
# =========================
STATE_MAP = {
    "Bengaluru": "Karnataka",
    "Kolkata": "West Bengal",
    "Delhi": "Delhi",
    "Mumbai": "Maharashtra"
}

def ai_loop():
    print("[AI] Weather Inspector started...")

    while True:
        try:
            print("[WEATHER] Checking weather intelligence...")
            weather = run_weather_check()

            if weather and "ai_generated_complaint" in weather:
                ai = weather["ai_generated_complaint"]
                
                # 🛑 FORCE SYSTEM ACTIVE LOCATION 🛑
                loc = get_active_location()
                city = loc.get("city", "Bengaluru")
                lat = loc.get("latitude")
                lon = loc.get("longitude")
                
                state = STATE_MAP.get(city, "Karnataka")
                area = city # Default to city for panchayat dashboard
                
                print(f"[AI LOCATION OVERRIDE] {state} {city} {area}")

                description = ai.get("description", "Weather-based civic risk detected")
                ai_res = analyze_complaint(description, lat, lon)

                save_complaint(
                    description,
                    ai_res.get("department"),
                    ai_res.get("priority"),
                    ai_res.get("risk_score"),
                    ai_res.get("explanation"),
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
                print("[INFO] Weather AI report synced with Panchayat")

        except Exception as e:
            print(f"[ERR] Weather loop error: {e}")

        time.sleep(60)

def sla_loop():
    print("[AI] SLA Monitoring active...")
    while True:
        try:
            enforce_sla()
        except Exception as e:
            print(f"[ERR] SLA loop error: {e}")
        time.sleep(3600)

def start_scheduler():
    t1 = threading.Thread(target=ai_loop, daemon=True)
    t1.start()
    t2 = threading.Thread(target=sla_loop, daemon=True)
    t2.start()