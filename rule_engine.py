def analyze_risk(text):
    score = 0
    explanation = []

    if "hospital" in text.lower():
        score += 30
        explanation.append("Detected hospital (+30)")

    if "water" in text.lower():
        score += 10
        explanation.append("Detected water issue (+10)")

    if score >= 70:
        priority = "HIGH"
        department = "Emergency Services"
    elif score >= 40:
        priority = "MEDIUM"
        department = "Drainage"
    else:
        priority = "LOW"
        department = "Municipality"

    return {
        "complaint": text,
        "priority": priority,
        "risk_score": score,
        "department": department,
        "explanation": explanation
    }
