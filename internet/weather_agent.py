import requests
from utils.signal_formatter import weather_to_complaint
from ai_agent import analyze_complaint

API_KEY = "7f0856d3df6f559d0714c87079e90c49"
CITY = "Assam"

def run_weather_check():
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={CITY}&appid={API_KEY}&units=metric"
    )

    try:
        r = requests.get(url, timeout=10)
        data = r.json()

        if r.status_code != 200:
            return {"status": "weather_api_failed", "error": data}

        complaint_text = weather_to_complaint(data)

        if complaint_text:
            return analyze_complaint(complaint_text)

        return {"status": "no_action_required", "weather": data["weather"][0]["main"]}

    except Exception as e:
        return {"status": "error", "message": str(e)}
