import requests
import os
from datetime import datetime
from ai_agent import analyze_complaint


API_KEY = os.getenv("WEATHER_API_KEY")

# ===============================
# 📍 GEO INTELLIGENCE
# ===============================
def get_city_from_coords(lat, lon):
    try:
        url = f"https://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=1&appid={API_KEY}"
        res = requests.get(url, timeout=10).json()
        return res[0]["name"] if res else "Unknown"
    except:
        return "Unknown"


# ===============================
# 🌤 CURRENT WEATHER
# ===============================
def get_current_weather(city):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    return requests.get(url).json()


# ===============================
# 🔮 FORECAST WEATHER
# ===============================
def get_forecast(city):
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={API_KEY}&units=metric"
    return requests.get(url).json()


# ===============================
# 🧠 RISK ENGINE
# ===============================
def calculate_risk(current, forecast):
    temp = current["main"]["temp"]
    condition = current["weather"][0]["main"]

    risk = "LOW"
    alerts = []

    # 🌧 Rain risk
    if "Rain" in condition:
        risk = "HIGH"
        alerts.append("Possible waterlogging")

    # 🔥 Heatwave
    if temp > 38:
        risk = "HIGH"
        alerts.append("Heatwave risk")

    # 🌪 Storm detection from forecast
    for slot in forecast["list"][:8]:  # next 24h
        if "Thunderstorm" in slot["weather"][0]["main"]:
            risk = "HIGH"
            alerts.append("Storm warning")
            break

    return risk, alerts


# ===============================
# 👥 CROWD INTELLIGENCE
# ===============================
def estimate_crowd_level():
    hour = datetime.now().hour

    if 8 <= hour <= 11:
        return "HIGH (Office rush)"
    elif 17 <= hour <= 20:
        return "HIGH (Evening rush)"
    elif 12 <= hour <= 16:
        return "MEDIUM"
    else:
        return "LOW"


# ===============================
# 🌍 MAIN INTELLIGENCE ENGINE
# ===============================
# ===============================
# 🌍 MAIN INTELLIGENCE ENGINE
# ===============================
def civic_intelligence(lat, lon):
    city = get_city_from_coords(lat, lon)

    current = get_current_weather(city)
    forecast = get_forecast(city)

    risk, alerts = calculate_risk(current, forecast)
    crowd = estimate_crowd_level()

    return {
        "city": city,
        "temperature": current["main"]["temp"],
        "condition": current["weather"][0]["main"],
        "risk_level": risk,
        "alerts": alerts,
        "crowd_level": crowd,
        "best_time_for_work": "Early morning" if crowd.startswith("HIGH") else "Now is good"
    }


# ===============================
# 🤖 AUTO COMPLAINT GENERATOR
# ===============================
def intelligence_to_complaint(lat, lon):
    data = civic_intelligence(lat, lon)

    complaint = None

    # 🌧 Flood risk
    if data["risk_level"] == "HIGH" and "waterlogging" in " ".join(data["alerts"]).lower():
        complaint = f"Waterlogging risk detected in {data['city']} due to rain"

    # 🔥 Heatwave
    elif data["risk_level"] == "HIGH" and data["temperature"] > 38:
        complaint = f"Extreme heatwave in {data['city']} — water supply and public safety risk"

    # 🌪 Storm
    elif any("storm" in a.lower() for a in data["alerts"]):
        complaint = f"Storm warning in {data['city']} — possible road damage and hazards"

    if complaint:
        print("🤖 Intelligence Complaint:", complaint)
        return analyze_complaint(complaint, lat, lon)

    return {
        "status": "no_action_required",
        "intelligence": data
    }