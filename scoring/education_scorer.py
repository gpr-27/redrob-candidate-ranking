"""
Education Scorer

Evaluates education quality and relevance for the AI/ML Engineer role.

JD doesn't explicitly require specific degrees, but:
- Relevant fields (CS, ML, Data Science, Statistics) are a plus
- Institution tier matters (IIT > NIT/IIIT > private > local)
- Higher degrees in relevant fields add value
- Education is a weak signal compared to career/skills
"""


# Relevant fields of study (normalized to lowercase)
HIGHLY_RELEVANT_FIELDS = {
    'machine learning', 'artificial intelligence', 'data science',
    'computer science', 'computer engineering', 'information technology',
    'statistics', 'computational linguistics', 'natural language processing',
}

MODERATELY_RELEVANT_FIELDS = {
    'mathematics', 'applied mathematics', 'physics',
    'electrical engineering', 'electronics',
    'information systems', 'software engineering',
}

IRRELEVANT_FIELDS = {
    'mechanical engineering', 'civil engineering', 'chemical engineering',
    'marketing', 'business administration', 'mba', 'commerce',
    'arts', 'humanities', 'history', 'political science',
    'biology', 'biotechnology', 'agriculture',
}

# Degree levels
DEGREE_WEIGHTS = {
    'ph.d': 1.0,
    'phd': 1.0,
    'm.tech': 0.9,
    'm.s.': 0.85,
    'm.sc': 0.8,
    'm.e.': 0.85,
    'mba': 0.5,
    'b.tech': 0.7,
    'b.e.': 0.7,
    'b.sc': 0.55,
    'b.com': 0.3,
    'b.a': 0.3,
    'diploma': 0.25,
}

# Tier scores
TIER_SCORES = {
    'tier_1': 1.0,   # IIT, IISC, top IIITs
    'tier_2': 0.75,  # NITs, BITS, good IIITs, SRM, VIT, etc.
    'tier_3': 0.45,  # Decent colleges
    'tier_4': 0.25,  # Local / unknown
    'unknown': 0.35,
}


def score_education(candidate: dict) -> float:
    """
    Score education quality on a 0-1 scale.

    Sub-components:
    A) Best institution tier
    B) Most relevant field of study
    C) Highest degree level
    """
    education = candidate.get('education', [])

    if not education:
        return 0.15  # No education data — mild penalty

    # A) Best institution tier
    best_tier = max(
        (TIER_SCORES.get(e.get('tier', 'unknown'), 0.35) for e in education),
        default=0.25
    )

    # B) Most relevant field
    best_field_score = 0.0
    for e in education:
        field = e.get('field_of_study', '').strip().lower()
        if field in HIGHLY_RELEVANT_FIELDS:
            best_field_score = max(best_field_score, 1.0)
        elif field in MODERATELY_RELEVANT_FIELDS:
            best_field_score = max(best_field_score, 0.5)
        elif field in IRRELEVANT_FIELDS:
            best_field_score = max(best_field_score, 0.15)
        else:
            best_field_score = max(best_field_score, 0.3)

    # C) Highest degree
    best_degree = 0.0
    for e in education:
        degree = e.get('degree', '').strip().lower()
        # Try exact match first
        if degree in DEGREE_WEIGHTS:
            best_degree = max(best_degree, DEGREE_WEIGHTS[degree])
        else:
            # Keyword match
            if 'ph.d' in degree or 'phd' in degree or 'doctor' in degree:
                best_degree = max(best_degree, 1.0)
            elif 'm.' in degree or 'master' in degree:
                best_degree = max(best_degree, 0.8)
            elif 'b.' in degree or 'bachelor' in degree:
                best_degree = max(best_degree, 0.6)
            else:
                best_degree = max(best_degree, 0.3)

    # Combine
    final = (
        0.35 * best_tier +
        0.40 * best_field_score +
        0.25 * best_degree
    )

    return round(min(final, 1.0), 4)
