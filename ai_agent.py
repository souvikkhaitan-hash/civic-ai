from datetime import datetime

print("[INFO] AI ENGINE v4.0 - Startup Intelligence Layer LOADED")

SYSTEM_USER_ID = 0

def calculate_risk(text, duplicate_count=0, created_at=None, department=None, source="user"):
    text = str(text).lower()
    score = 0
    reasons = []

    # --------------------------
    # 1. SEVERITY
    # --------------------------
    if any(k in text for k in ["death", "blast", "collapse", "electrocution", "ambulance", "dead"]):
        score += 60
        reasons.append("Critical Hazard/Life Risk (+60)")
    elif any(k in text for k in ["fire", "accident", "emergency"]):
        score += 50
        reasons.append("High Severity Incident (+50)")
    elif any(k in text for k in ["flood", "electricity", "short circuit", "wire", "shock"]):
        score += 30
        reasons.append("Infrastructure/Safety Risk (+30)")

    # --------------------------
    # 2. URGENCY
    # --------------------------
    if any(k in text for k in ["urgent", "immediately", "asap", "fast"]):
        score += 20
        reasons.append("Urgency Keyword detected (+20)")

    if any(k in text for k in ["again", "still", "not fixed", "repeated", "worst"]):
        score += 15
        reasons.append("Recurring/Neglected Issue (+15)")

    # --------------------------
    # 3. DUPLICATE DENSITY
    # --------------------------
    if duplicate_count >= 5:
        score += 40
        reasons.append(f"Critical Cluster: {duplicate_count}+ reports (+40)")
    elif duplicate_count >= 3:
        score += 25
        reasons.append("Moderate Cluster: 3+ reports (+25)")
    elif duplicate_count >= 1:
        score += 10
        reasons.append("Duplicate report detected (+10)")

    # --------------------------
    # 4. TIME ESCALATION
    # --------------------------
    if created_at:
        try:
            if isinstance(created_at, str):
                dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            else:
                dt = created_at
                
            hours = (datetime.now() - dt).total_seconds() / 3600
            if hours > 48:
                score += 30
                reasons.append("Breached threshold: 48h ignored (+30)")
            elif hours > 24:
                score += 15
                reasons.append("Attention required: 24h old (+15)")
        except:
            pass

    # --------------------------
    # 5. LOCATION SENSITIVITY
    # --------------------------
    if any(k in text for k in ["hospital", "medical", "clinic"]):
        score += 30
        reasons.append("Critical zone: Hospital/Medical (+30)")
    elif any(k in text for k in ["school", "college", "children"]):
        score += 25
        reasons.append("Sensitive zone: Educational Area (+25)")
    elif any(k in text for k in ["main road", "highway", "junction", "cross"]):
        score += 20
        reasons.append("High Traffic Zone: Junction/Main Road (+20)")

    # --------------------------
    # 6. DEPARTMENT CRITICALITY
    # --------------------------
    if department:
        d = department.lower()
        if d == "electricity" or d == "electric":
            score += 25
            reasons.append("Department: Power/Electricity (+25)")
        elif d == "water":
            score += 20
            reasons.append("Department: Water Supply (+20)")
        elif d == "roads":
            score += 15
            reasons.append("Department: Infrastructure (+15)")
        elif d == "sanitation":
            score += 10
            reasons.append("Department: Sanitation (+10)")

    # --------------------------
    # 7. AI SOURCE BOOST
    # --------------------------
    if source and source != "user":
        score += 20
        reasons.append(f"Source: {source.upper()} Auto-Discovery (+20)")

    if not reasons: 
        score += 10
        reasons.append("Base civic priority (+10)")
    
    final_score = min(score, 100)
    return final_score, reasons

def analyze_complaint(complaint_text, lat=None, lon=None):
    text = complaint_text.lower()
    department = "General"

    # Quick Department Mapping
    if any(w in text for w in ["water", "leak", "pipe"]): department = "Water"
    elif any(w in text for w in ["garbage", "waste", "trash", "dump"]): department = "Sanitation"
    elif any(w in text for w in ["light", "power", "electric", "electrician", "wire"]): department = "Electric"
    elif any(w in text for w in ["pothole", "road", "street"]): department = "Roads"
    elif any(w in text for w in ["drain", "flood", "sewage"]): department = "Drainage"

    # Use calculate_risk with default params for initial AI assessment
    score, reasons = calculate_risk(text, department=department)
    
    # Priority Mapping
    if score >= 70: priority = "HIGH"
    elif score >= 40: priority = "MEDIUM"
    else: priority = "LOW"

    return {
        "department": department,
        "priority": priority,
        "risk_score": score,
        "explanation": reasons,
        "latitude": lat,
        "longitude": lon
    }