import json

from database import (
    save_complaint,
    find_similar_open_complaint,
    escalate_complaint
)

DEMO_MODE = False

# System user for AI-generated complaints
SYSTEM_USER_ID = 0


def analyze_complaint(complaint_text):
    score = 0
    explanation = []
    text = complaint_text.lower()

    # ==============================
    # 🔍 SMART SCORING ENGINE
    # ==============================

    water_keywords = [
        "water", "flood", "flooded",
        "drain", "overflow", "logging"
    ]

    # Flooding detection
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

    # Base civic risk
    if score > 0:
        score += 5
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
    # 🔁 DUPLICATE DETECTION
    # ==============================
    keyword = None
    for w in water_keywords:
        if w in text:
            keyword = w
            break

    existing = find_similar_open_complaint(keyword) if keyword else None

    # ==============================
    # 🔁 MERGE DUPLICATES (FIXED)
    # ==============================
    if existing:
        existing_id = existing["id"]
        old_score = existing["risk_score"]
        old_explanation = existing["explanation"]

        # Safe int conversion
        try:
            old_score = int(old_score)
        except:
            old_score = 0

        # Smart merge with cap (PRODUCTION SAFE)
        merged_score = old_score + int(score * 0.5)

        # HARD CAP (prevents 1000+ scores)
        new_score = min(merged_score, 100)

        # Safe JSON load
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
            "status": "IN_PROGRESS",
            "department": department,
            "priority": "HIGH"
        }

    # ==============================
    # 🆕 NEW COMPLAINT
    # ==============================
    save_complaint(
        complaint_text,
        department,
        priority,
        score,
        explanation,
        SYSTEM_USER_ID  # AI system complaints
    )

    return {
        "complaint": complaint_text,
        "department": department,
        "priority": priority,
        "risk_score": score,
        "status": status,
        "explanation": explanation
    }