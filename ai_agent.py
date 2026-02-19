import json

from database import (
    save_complaint,
    find_similar_open_complaint,
    escalate_complaint
)

DEMO_MODE = True


def analyze_complaint(complaint_text):
    score = 0
    explanation = []
    text = complaint_text.lower()

    # ==============================
    # 🔍 SMART SCORING ENGINE
    # ==============================

    # Flooding / drainage detection
    water_keywords = [
        "water", "flood", "flooded",
        "drain", "overflow", "logging"
    ]
    if any(w in text for w in water_keywords):
        score += 15
        explanation.append("Detected flooding/water issue (+15)")

    # Traffic disruption
    if any(w in text for w in ["traffic", "road", "vehicles", "blocked"]):
        score += 10
        explanation.append("Traffic disruption detected (+10)")

    # Emergency zones
    if "ambulance" in text or "hospital" in text:
        score += 40
        explanation.append("Emergency zone detected (+40)")

    # Bonus severity booster
    if score > 0:
        score += 5  # ensures no score becomes 0
        explanation.append("Base civic risk added (+5)")

    # ==============================
    # 🎯 PRIORITY MAPPING
    # ==============================
    if score >= 70:
        priority = "HIGH"
        status = "IN_PROGRESS"
    elif score >= 40:
        priority = "MEDIUM"
        status = "OPEN"
    else:
        priority = "LOW"
        status = "OPEN"

    # ==============================
    # 🏢 DEPARTMENT DETECTION
    # ==============================
    department = "Drainage" if any(w in text for w in water_keywords) else "General"

    # ==============================
    # 🔁 SMART DUPLICATE GROUPING
    # ==============================
    keyword = None
    for w in water_keywords:
        if w in text:
            keyword = w
            break

    existing = find_similar_open_complaint(keyword) if keyword else None

    # ==============================
    # 🔁 MERGE DUPLICATES
    # ==============================
    if existing:
        existing_id, old_score, old_explanation = existing

        # Safe int conversion
        try:
            old_score = int(old_score)
        except:
            old_score = 0

        new_score = old_score + score

        # Safe JSON explanation load
        try:
            old_exp_list = json.loads(old_explanation) if old_explanation else []
        except:
            old_exp_list = []

        combined_explanation = old_exp_list + explanation
        combined_explanation.append("Merged duplicate complaint")

        escalate_complaint(existing_id, new_score, combined_explanation)

        return {
            "message": "Duplicate complaint merged",
            "complaint_id": existing_id,
            "risk_score": new_score,
            "status": "IN_PROGRESS"
        }

    # ==============================
    # 🆕 NEW COMPLAINT
    # ==============================
    save_complaint(
        complaint_text,
        department,
        priority,
        score,
        explanation
    )

    return {
        "complaint": complaint_text,
        "department": department,
        "priority": priority,
        "risk_score": score,
        "status": status,
        "explanation": explanation
    }
