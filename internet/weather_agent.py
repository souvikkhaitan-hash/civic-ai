import requests
import os
from dotenv import load_dotenv
from ai_agent import analyze_complaint

# 🔥 LOAD ENV FIRST
load_dotenv()

API_KEY = os.getenv("WEATHER_API_KEY")
CITY = os.getenv("DEFAULT_CITY", "Kolkata")

DEFAULT_LAT = 12.9716
DEFAULT_LON = 77.5946


def run_weather_check():
    try:
        if not API_KEY:
            return {"status": "missing_api_key"}

        # 🌦 Current weather
        current_url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={CITY}&appid={API_KEY}&units=metric"
        )

        forecast_url = (
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?q={CITY}&appid={API_KEY}&units=metric"
        )

        current = requests.get(current_url, timeout=10).json()
        forecast = requests.get(forecast_url, timeout=10).json()

        if "main" not in current:
            return {"status": "weather_api_failed", "error": current}

        temp = current["main"]["temp"]
        condition = current["weather"][0]["main"].lower()

        # 🌧 Analyze forecast (next 24h)
        rain_chance = 0
        if "list" in forecast:
            next_8 = forecast["list"][:8]
            rain_chance = sum(
                1 for slot in next_8
                if "rain" in slot.get("weather", [{}])[0]["main"].lower()
            )

        complaint = None

        # 🤖 Smart rules
        if rain_chance >= 4:
            complaint = "Heavy rain forecast — possible flooding in city areas"
        elif condition in ["rain", "thunderstorm","clear"]:
            complaint = "Ongoing rain detected — waterlogging risk"
        elif temp > 40:
            complaint = "Extreme heatwave detected — water shortage risk"
        elif temp < 5:
            complaint = "Severe cold conditions — shelter support needed"

        if complaint:
            print("🤖 Weather AI Complaint:", complaint)
            ai_result = analyze_complaint(complaint, lat=DEFAULT_LAT, lon=DEFAULT_LON)
            ai_result["description"] = complaint # Ensure scheduler finds the text
            return {
                "weather": {
                    "temp": temp,
                    "condition": condition,
                    "forecast_rain_slots": rain_chance
                },
                "ai_generated_complaint": ai_result
            }

        return {
            "status": "no_action_required",
            "temp": temp,
            "condition": condition,
            "forecast_rain_slots": rain_chance
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def weather_intelligence(city_name=None):
    target_city = city_name or CITY
    url = f"https://api.openweathermap.org/data/2.5/weather?q={target_city}&appid={API_KEY}&units=metric"
    r = requests.get(url, timeout=10)
    data = r.json()

    if r.status_code != 200:
        return {"error": data}

    temp = data["main"]["temp"]
    condition = data["weather"][0]["main"]

    risk = "LOW"
    if condition.lower() in ["rain", "thunderstorm",]:
        risk = "HIGH"
    elif temp > 38:
        risk = "MEDIUM"

    return {
        "city": target_city,
        "temperature": temp,
        "condition": condition,
        "risk_level": risk
    }