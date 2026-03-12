def is_civic_issue(text: str) -> bool:
    text = text.lower()

    # 🚫 HARD BLOCK — Not civic infra
    banned_topics = [
        "rape", "murder", "gang", "arrest",
        "celebrity", "movie", "politics",
        "election", "minister", "scam",
        "fraud", "bitcoin", "startup funding"
    ]

    if any(word in text for word in banned_topics):
        return False

    # ✅ Civic keywords
    civic_keywords = [
        "road", "pothole", "garbage", "waste",
        "drain", "water", "flood", "traffic",
        "street light", "power cut", "sewage",
        "public transport", "bus stop"
    ]

    return any(word in text for word in civic_keywords)