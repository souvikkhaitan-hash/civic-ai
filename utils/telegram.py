import requests

# TELEGRAM BOT CONFIG
BOT_TOKEN = "8204492778:AAE2nSJshHM9LxVxe7Ov90lJO1crxhB9ud4"
CHAT_ID = "1969099550"

def send_telegram(message):
    """Sends a real-time notification to the administrator via Telegram."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }

        response = requests.post(url, data=payload)
        
        if response.status_code == 200:
            print("[TELEGRAM SUCCESS] Notification sent to Admin")
        else:
            print(f"[TELEGRAM ERROR] Status: {response.status_code}, Body: {response.text}")

    except Exception as e:
        print("[TELEGRAM FAILED] Connection Error:", e)
