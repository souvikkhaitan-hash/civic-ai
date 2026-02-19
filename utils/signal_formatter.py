def weather_to_complaint(data):
    weather = data.get("weather", [])
    rain = data.get("rain")

    if rain or any("rain" in w["description"].lower() for w in weather):
        city = data.get("name", "Unknown Area")
        return (
            f"Heavy rainfall detected in {city}. "
            f"High risk of water logging and traffic disruption."
        )

    return None
