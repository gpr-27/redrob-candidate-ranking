"""
Experience Scorer

Evaluates whether a candidate's years of experience match the JD's
5-9 year sweet spot, with 4-5 years in applied ML/AI roles.

JD says:
- "5-9 years" is a range, not a requirement
- Some hit senior judgment at 4, some never after 15
- Strongly prefer 6-8 total, 4-5 in applied ML/AI at product companies
"""


def score_experience(candidate: dict) -> float:
    """
    Score years of experience fit on a 0-1 scale.

    The JD sweet spot is 5-9 years. We model this as a bell curve
    centered around 7 years.
    """
    yoe = candidate['profile']['years_of_experience']

    # Sweet spot: 5-9 years, ideal around 6-8
    if 5.5 <= yoe <= 8.5:
        exp_score = 1.0
    elif 5.0 <= yoe <= 9.0:
        exp_score = 0.95
    elif 4.0 <= yoe <= 10.0:
        exp_score = 0.8
    elif 3.0 <= yoe <= 12.0:
        exp_score = 0.6
    elif 2.0 <= yoe <= 15.0:
        exp_score = 0.4
    elif yoe > 15.0:
        exp_score = 0.25
    else:
        exp_score = 0.15  # < 2 years — too junior

    return round(exp_score, 4)
