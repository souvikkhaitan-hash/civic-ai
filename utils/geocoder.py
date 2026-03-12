import requests
import time

def geocode(lat, lon):
    """
    Converts latitude and longitude into a readable address using Nominatim API.
    Returns the address string or None if it fails.
    """
    if lat is None or lon is None:
        return None
        
    try:
        # Nominatim requires a User-Agent header
        headers = {
            'User-Agent': 'CivicAI-ComplaintSystem/1.0'
        }
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('display_name')
            
    except Exception as e:
        print(f"Geocoding error: {e}")
        
    return None
