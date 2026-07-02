"""
Title & Role Fit Scorer

Determines how well a candidate's current (and past) titles align with the
Senior AI/ML Engineer role described in the JD.

Key insight from JD: "A candidate who has all the AI keywords listed as skills
but whose title is 'Marketing Manager' is not a fit, no matter how perfect
their skill list looks."
"""


# ── Title tiers (higher = better fit for Senior AI/ML Engineer) ─────────────

# Tier 5: Direct match — these people *are* what the JD describes
TIER_5_TITLES = {
    'senior machine learning engineer', 'staff machine learning engineer',
    'lead ai engineer', 'senior ai engineer', 'applied ml engineer',
    'machine learning engineer', 'senior data scientist',
    'senior nlp engineer', 'senior applied scientist',
    'search engineer', 'recommendation systems engineer',
    'senior ml engineer — search & ranking',
}

# Tier 4: Very close — strong ML/AI practitioners
TIER_4_TITLES = {
    'ml engineer', 'ai engineer', 'ai research engineer', 'data scientist',
    'ai specialist', 'senior software engineer (ml)',
    'nlp engineer', 'junior ml engineer',
}

# Tier 3: Adjacent technical — could be strong with right career history
TIER_3_TITLES = {
    'senior data engineer', 'senior software engineer', 'data engineer',
    'analytics engineer', 'backend engineer',
}

# Tier 2: Technical but further away — needs strong ML signals elsewhere
TIER_2_TITLES = {
    'software engineer', 'full stack developer', 'cloud engineer',
    'java developer', 'devops engineer', 'frontend engineer',
    '.net developer', 'mobile developer', 'qa engineer', 'data analyst',
}

# Tier 1: Non-technical — almost never a fit
TIER_1_TITLES = {
    'business analyst', 'hr manager', 'mechanical engineer', 'accountant',
    'project manager', 'customer support', 'operations manager',
    'content writer', 'sales executive', 'civil engineer',
    'graphic designer', 'marketing manager', 'computer vision engineer',
}


def _normalize_title(title: str) -> str:
    """Lowercase and strip a title for matching."""
    return title.strip().lower()


def _title_tier(title: str) -> int:
    """Return the tier (1-5) for a given title string."""
    t = _normalize_title(title)
    if t in TIER_5_TITLES:
        return 5
    if t in TIER_4_TITLES:
        return 4
    if t in TIER_3_TITLES:
        return 3
    if t in TIER_2_TITLES:
        return 2
    if t in TIER_1_TITLES:
        return 1
    # Fallback: keyword-based heuristic
    ml_kw = ['ml', 'machine learning', 'ai ', 'artificial intelligence',
             'data scientist', 'deep learning', 'nlp']
    if any(kw in t for kw in ml_kw):
        return 4
    tech_kw = ['engineer', 'developer', 'architect', 'scientist', 'sde']
    if any(kw in t for kw in tech_kw):
        return 2
    return 1


def score_title(candidate: dict) -> float:
    """
    Score a candidate's title/role fit on a 0-1 scale.

    We look at:
    1. Current title (strongest signal)
    2. Best title in career history (shows trajectory)
    """
    profile = candidate['profile']
    career = candidate['career_history']

    # Current title tier
    current_tier = _title_tier(profile['current_title'])

    # Best historical title tier (trajectory matters)
    best_career_tier = max((_title_tier(ch['title']) for ch in career), default=1)

    # Current title matters most (70%), best ever (30%)
    # This catches someone who was an ML Engineer but is now a PM (still relevant)
    combined_tier = 0.70 * current_tier + 0.30 * best_career_tier

    # Map tier (1-5) to score (0-1)
    # Tier 5 → 1.0, Tier 4 → 0.85, Tier 3 → 0.55, Tier 2 → 0.25, Tier 1 → 0.0
    tier_scores = {
        5: 1.0,
        4: 0.85,
        3: 0.55,
        2: 0.25,
        1: 0.0,
    }

    # Weighted combination: interpolate based on combined_tier
    # For combined values, linearly interpolate between tiers
    lower = int(combined_tier)
    upper = min(lower + 1, 5)
    frac = combined_tier - lower
    lower = max(lower, 1)

    score = tier_scores[lower] * (1 - frac) + tier_scores[upper] * frac

    return round(score, 4)
