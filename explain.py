def generate_explanation(matched_rules, score):
    explanation = []

    for rule, value in matched_rules:
        explanation.append(f"Detected '{rule}' (+{value})")

    if score < 30:
        explanation.append("Overall risk is low")
    elif score < 60:
        explanation.append("Moderate risk situation")
    else:
        explanation.append("High risk – immediate attention required")

    return explanation
