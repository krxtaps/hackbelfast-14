import re

with open("services/police_data_scoring.py", "r") as f:
    content = f.read()

if "import math" not in content:
    content = "import math\n" + content

old_func = '''def calculate_score_from_crimes(crimes: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    """
    Calculates a safety score and provides explanations based on the crimes array.
    Returns (score, explanations).
    """
    if not crimes:
        return 100, ["No recent crimes reported in this immediate area.", "Generally safe area."]

    total_crimes = len(crimes)
    total_penalty = 0
    category_counts = Counter()

    for crime in crimes:
        category = crime.get("category", "other-crime")
        category_counts[category] += 1
        weight = CRIME_WEIGHTS.get(category, DEFAULT_WEIGHT)
        total_penalty += weight * SCALE_FACTOR

    # Calculate final score clamped between 0 and 100
    score = max(0, min(100, int(100 - total_penalty)))

    # Generate explanations
    explanations = []
    explanations.append(f"{total_crimes} nearby crime(s) reported recently.")'''

new_func = '''def calculate_score_from_crimes(crimes: List[Dict[str, Any]], business_count: int = 0) -> Tuple[int, List[str]]:
    """
    Calculates a safety score and provides explanations based on the crimes array,
    normalized by business density (footfall proxy) and using a logarithmic scale
    to prevent penalizing busy areas linearly.
    Returns (score, explanations).
    """
    if not crimes:
        return 100, ["No recent crimes reported in this immediate area.", "Generally safe area."]

    total_crimes = len(crimes)
    total_penalty = 0
    category_counts = Counter()

    for crime in crimes:
        category = crime.get("category", "other-crime")
        category_counts[category] += 1
        weight = CRIME_WEIGHTS.get(category, DEFAULT_WEIGHT)
        total_penalty += weight * SCALE_FACTOR

    # 1. Logarithmic Crime Scaling
    # Instead of linear penalty (e.g., 50 crimes = -100 points), 
    # we soften the blow of sheer volume. log1p(50)*16 = ~62 penalty.
    log_penalty = math.log1p(total_penalty) * 16.0

    # 2. Footfall Proxy Normalization (Business Density)
    # The more businesses near the street, the higher the natural foot traffic,
    # meaning the crime rate per capita is actually much lower.
    # 0 businesses -> divide by 1.0 (no discount)
    # 20 businesses -> log1p(20) * 0.15 = divide by ~1.45
    # 50 businesses -> log1p(50) * 0.15 = divide by ~1.59
    density_discount = max(1.0, 1.0 + (math.log1p(business_count) * 0.15))
    
    final_penalty = log_penalty / density_discount

    # Calculate final score clamped between 0 and 100
    score = max(0, min(100, int(100 - final_penalty)))

    # Generate explanations
    explanations = []
    explanations.append(f"{total_crimes} nearby crime(s) reported recently.")
    if business_count > 5:
        explanations.append(f"Crime impact normalized for high-footfall area ({business_count} active venues).")'''

content = content.replace(old_func, new_func)

with open("services/police_data_scoring.py", "w") as f:
    f.write(content)
