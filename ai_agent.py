print("[INFO] AI ENGINE v3.1 LOADED")

SYSTEM_USER_ID = 0

def analyze_complaint(complaint_text, lat=None, lon=None):
    text = complaint_text.lower()
    score = 0
    explanation = []
    department = "General"

    # =========================
    # 🚨 EMERGENCY LAYER
    # =========================
    if any(w in text for w in ["ambulance", "dead", "death", "electrocution"]):
        score += 50
        explanation.append("Emergency keyword (+50)")

    if "accident" in text:
        score += 25
        explanation.append("Accident risk (+25)")

    # =========================
    # 🌊 WATER / FLOOD
    # =========================
    water_words = ["water", "flood", "drain", "overflow", "waterlogging", "sewage"]
    if any(w in text for w in water_words):
        score += 20
        department = "Drainage"
        explanation.append("Water/drainage issue (+20)")

    # =========================
    # 🛣 ROAD INFRA
    # =========================
    if any(w in text for w in ["pothole", "road damage", "bad road"]):
        score += 30
        department = "Roads"
        explanation.append("Road hazard (+30)")

    # Accident + pothole combo boost
    if "pothole" in text and "accident" in text:
        score += 15
        explanation.append("Accident caused by pothole (+15)")

    # =========================
    # 🚦 TRAFFIC
    # =========================
    if any(w in text for w in ["traffic", "jam", "blocked", "congestion"]):
        score += 15
        explanation.append("Traffic disruption (+15)")

    # =========================
    # 🗑 SANITATION
    # =========================
    if any(w in text for w in ["garbage", "waste", "trash", "dump"]):
        score += 25
        department = "Sanitation"
        explanation.append("Garbage hygiene risk (+25)")

    # =========================
    # ⚡ ELECTRIC
    # =========================
    if any(w in text for w in ["street light", "no light", "dark road", "power cut"]):
        score += 20
        department = "Electric"
        explanation.append("Lighting/electric risk (+20)")

    # =========================
    # 🧠 SEVERITY BOOSTERS
    # =========================
    if any(w in text for w in ["school", "hospital", "market"]):
        score += 10
        explanation.append("Public hotspot (+10)")

    if any(w in text for w in ["many", "multiple", "daily", "everyday", "for days"]):
        score += 10
        explanation.append("Recurring issue (+10)")

    # =========================
    # BASE CIVIC RISK
    # =========================
    if score > 0:
        score += 5
        explanation.append("Base civic risk (+5)")

    # =========================
    # PRIORITY MAPPING
    # =========================
    if score >= 70:
        priority = "HIGH"
    elif score >= 35:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "department": department,
        "priority": priority,
        "risk_score": score,
        "explanation": explanation,
        "latitude": lat,
        "longitude": lon
    }