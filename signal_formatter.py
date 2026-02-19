def weather_to_complaint(data):
    weather = data.get("weather", [])
    rain = data.get("rain")
    wind = data.get("wind", {})
    temp = data.get("main", {}).get("temp", 0)
    city = data.get("name", "Unknown Area")

    descriptions = [w["description"].lower() for w in weather]

    # 🌧 Rain / Flood risk
    if rain or any("rain" in d for d in descriptions):
        return (
            f"Heavy rainfall detected in {city}. "
            f"Water logging reported near hospital and roads blocked."
        )

    # 🌫 Air quality / haze
    if any("haze" in d or "smoke" in d for d in descriptions):
        return (
            f"Severe air pollution in {city}. "
            f"Hospital admissions increasing due to breathing issues."
        )

    # 💨 Strong wind
    if wind.get("speed", 0) > 10:
        return (
            f"Strong winds in {city}. "
            f"Trees fallen and road blockage reported causing traffic delay."
        )

    # 🔥 Heat wave
    if temp > 38:
        return (
            f"Extreme heat in {city}. "
            f"Water shortage complaints rising across residential areas."
        )

    return None
