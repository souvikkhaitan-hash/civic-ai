import time
import random
import threading
from internet.weather_agent import run_weather_check
from ai_agent import analyze_complaint

DEMO_COMPLAINTS = [
    "Water logging delaying ambulance movement",
    "Blocked drainage causing traffic disruption",
    "Severe water overflow near marketplace",
    "Flooded underpass blocking vehicles"
]

def ai_loop():
    print("🚀 AI Scheduler started...")

    while True:
        print("🌦 Checking weather...")
        weather = run_weather_check()
        print("Weather:", weather)

        time.sleep(200)  # every 15 seconds


def start_scheduler():
    thread = threading.Thread(target=ai_loop)
    thread.daemon = True
    thread.start()
