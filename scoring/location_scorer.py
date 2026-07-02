"""
Location & Logistics Scorer

Evaluates candidate location, work mode preference, and relocation willingness
against JD requirements.

JD says:
- "Pune/Noida-preferred but flexible"
- "Candidates in Hyderabad, Pune, Mumbai, Delhi NCR welcome"
- "Outside India: case-by-case, but we don't sponsor work visas"
- Work mode: Offices in Noida and Pune, used Tue/Thu, quarterly offsites
- "Notice period: We'd love sub-30-day notice. We can buy out up to 30 days."
"""

# Preferred cities (normalized to lowercase)
PREFERRED_CITIES = {'noida', 'pune'}
GOOD_CITIES = {'hyderabad', 'mumbai', 'delhi', 'gurgaon', 'gurugram',
               'bangalore', 'bengaluru', 'chennai', 'kolkata', 'new delhi'}
# State/region indicators for NCR
NCR_INDICATORS = {'uttar pradesh', 'haryana', 'delhi ncr', 'ncr', 'delhi'}


def _parse_location(location: str) -> tuple:
    """Extract city and region from location string like 'Noida, Uttar Pradesh'."""
    parts = [p.strip().lower() for p in location.split(',')]
    city = parts[0] if parts else ''
    region = parts[1] if len(parts) > 1 else ''
    return city, region


def score_location(candidate: dict) -> float:
    """
    Score location/logistics fit on a 0-1 scale.

    Sub-components:
    A) Country — India strongly preferred
    B) City — Pune/Noida preferred, other metros acceptable
    C) Work mode — flexible/hybrid/onsite preferred (they have offices)
    D) Relocation willingness
    E) Salary expectations — reasonable for the market
    """
    profile = candidate['profile']
    signals = candidate['redrob_signals']

    country = profile['country'].strip()
    city, region = _parse_location(profile['location'])

    # A) Country
    if country == 'India':
        country_score = 1.0
    elif country in ('Singapore', 'UAE'):
        country_score = 0.3  # Close timezone, but visa issues
    else:
        country_score = 0.15  # USA, Canada, UK, Germany, Australia — no sponsorship

    # B) City
    if city in PREFERRED_CITIES:
        city_score = 1.0
    elif city in GOOD_CITIES or region in NCR_INDICATORS:
        city_score = 0.75
    elif country == 'India':
        city_score = 0.5  # Other Indian city
    else:
        city_score = 0.2  # Foreign city

    # C) Work mode
    work_mode = signals['preferred_work_mode']
    if work_mode in ('flexible', 'hybrid'):
        mode_score = 1.0  # Matches company's Tue/Thu office + async style
    elif work_mode == 'onsite':
        mode_score = 0.85  # Also fine, they have offices
    else:  # remote
        mode_score = 0.6  # Acceptable but less ideal for quarterly offsites

    # D) Relocation willingness (only matters if not in preferred location)
    willing = signals['willing_to_relocate']
    if city in PREFERRED_CITIES:
        relocation_score = 1.0  # Already there
    elif willing:
        relocation_score = 0.85
    elif city in GOOD_CITIES:
        relocation_score = 0.6  # Good city, not willing to move, but might not need to
    else:
        relocation_score = 0.3

    # E) Salary expectations
    salary = signals['expected_salary_range_inr_lpa']
    sal_min = salary.get('min', 0)
    sal_max = salary.get('max', 0)
    # For a Senior AI/ML Engineer, 25-65 LPA is reasonable range
    if sal_max <= 65 and sal_min >= 15:
        salary_score = 1.0
    elif sal_max <= 80:
        salary_score = 0.8
    elif sal_max <= 100:
        salary_score = 0.6
    elif sal_min < 10:
        salary_score = 0.7  # Suspiciously low for this role
    else:
        salary_score = 0.4  # Very high expectations

    # Combine
    final = (
        0.35 * country_score +
        0.25 * city_score +
        0.10 * mode_score +
        0.15 * relocation_score +
        0.15 * salary_score
    )

    return round(min(final, 1.0), 4)
