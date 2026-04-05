import requests

# FAST2SMS CONFIG (Get from fast2sms.com)
API_KEY = "PASTE_YOUR_FAST2SMS_API_KEY_HERE"
ENABLE_SMS = True

def send_sms(mobile, message):
    if not ENABLE_SMS:
        print("[SMS DISABLED] Mode: OFF")
        return

    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        
        headers = {
            'authorization': API_KEY
        }

        data = {
            "route": "q",
            "message": message,
            "language": "english",
            "numbers": str(mobile)
        }

        response = requests.post(url, data=data, headers=headers)
        
        # Log success/failure
        res_json = response.json()
        if res_json.get("return"):
            print(f"[SMS SUCCESS] ID: {res_json.get('request_id')} -> {mobile}")
        else:
            print(f"[SMS API ERROR] {res_json.get('message')} -> {mobile}")

    except Exception as e:
        print("[SMS FAILED] Connection Error:", e)
        print(f"[SMS FALLBACK] To {mobile}: {message}")
