"""
Honeypot Detector

The dataset contains ~80 honeypot candidates with subtly impossible profiles.
Examples from the spec:
- "8 years of experience at a company founded 3 years ago"
- "'Expert' proficiency in 10 skills with 0 years used"

These are forced to relevance tier 0 in ground truth. Having >10% honeypots
in top-100 causes disqualification.

This module identifies likely honeypots and assigns a penalty multiplier.

Detection signals:
1. Expert skills with 0 duration months
2. Massive all-expert skill counts with near-zero average duration
3. Stated years_of_experience impossible vs career history timeline
4. Non-technical title paired with a deep ML skill stack
5. High endorsements on skills with 0 duration
6. Profile summary claiming work the title contradicts
7. Career stint STARTING BEFORE THE COMPANY WAS FOUNDED (the spec's own
   canonical example) — uses a public-knowledge founding-year table
8. years_of_experience exceeding the span since the earliest career start
9. Summary text stating a different experience number than the profile field
"""

import re
from datetime import datetime

REFERENCE_DATE = datetime(2026, 6, 1)

# Public-knowledge founding years for real companies appearing in the dataset.
# Only companies whose founding year is well-established are listed; fictional
# companies (Hooli, Initech, ...) obviously cannot be checked.
COMPANY_FOUNDED_YEAR = {
    'krutrim': 2023,
    'sarvam ai': 2023,
    'glance': 2019,
    'rephrase.ai': 2019,
    'observe.ai': 2017,
    'saarthi.ai': 2017,
    'aganitha': 2017,
    'cred': 2018,
    'niramai': 2016,
    'yellow.ai': 2016,
    'verloop.io': 2016,
    'wysa': 2015,
    'locobuzz': 2015,
    'meesho': 2015,
    'phonepe': 2015,
    'pharmeasy': 2015,
    'unacademy': 2015,
    'upgrad': 2015,
    'razorpay': 2014,
    'swiggy': 2014,
    'vedantu': 2014,
    'haptik': 2013,
    'mad street den': 2013,
    'nykaa': 2012,
    "byju's": 2011,
}

_SUMMARY_YEARS_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:\+\s*)?years')


def _compute_honeypot_signals(candidate: dict) -> dict:
    """
    Compute various honeypot detection signals.
    Returns a dict of signal_name → severity (0 = no issue, higher = more suspicious).
    """
    signals = {}
    profile = candidate['profile']
    career = candidate['career_history']
    skills = candidate['skills']
    redrob = candidate['redrob_signals']

    # ── Signal 1: Expert skills with 0 duration months ────────────────────
    expert_zero = sum(
        1 for s in skills
        if s['proficiency'] == 'expert' and s.get('duration_months', 1) == 0
    )
    signals['expert_zero_duration'] = expert_zero

    # ── Signal 2: Massive skill count with all-expert proficiency ─────────
    # Only suspicious if expert skills also have very low average durations
    expert_skills = [s for s in skills if s['proficiency'] == 'expert']
    expert_count = len(expert_skills)
    if len(skills) >= 10 and expert_count >= 8:
        avg_expert_dur = sum(s.get('duration_months', 0) for s in expert_skills) / max(expert_count, 1)
        # Only flag if average duration is suspiciously low (< 6 months)
        if avg_expert_dur < 6:
            signals['all_expert_many_skills'] = expert_count
        else:
            signals['all_expert_many_skills'] = 0
    else:
        signals['all_expert_many_skills'] = 0

    # ── Signal 3: Career duration impossibility ───────────────────────────
    # Check if stated experience years far exceeds actual career months
    total_career_months = sum(ch['duration_months'] for ch in career)
    stated_months = profile['years_of_experience'] * 12
    if stated_months > 0 and total_career_months > 0:
        if stated_months > total_career_months * 2 + 24:
            signals['experience_inflation'] = stated_months - total_career_months
        else:
            signals['experience_inflation'] = 0
    else:
        signals['experience_inflation'] = 0

    # ── Signal 4: Title-skills mismatch ───────────────────────────────────
    # Non-technical title but tons of deep ML skills
    title = profile['current_title'].lower()
    non_tech_titles = {
        'marketing manager', 'hr manager', 'accountant', 'sales executive',
        'operations manager', 'content writer', 'customer support',
        'graphic designer', 'civil engineer', 'mechanical engineer',
    }

    ml_core_skills = {
        'pytorch', 'tensorflow', 'deep learning', 'machine learning',
        'nlp', 'faiss', 'pinecone', 'weaviate', 'embeddings',
        'sentence transformers', 'rag', 'fine-tuning llms', 'qlora',
    }

    is_non_tech = title in non_tech_titles
    ml_skill_count = sum(
        1 for s in skills
        if s['name'].lower() in ml_core_skills
    )

    if is_non_tech and ml_skill_count >= 5:
        signals['title_skill_mismatch'] = ml_skill_count
    else:
        signals['title_skill_mismatch'] = 0

    # ── Signal 5: Extremely high endorsements with 0 duration ─────────────
    high_endorse_zero_dur = sum(
        1 for s in skills
        if s.get('endorsements', 0) > 30 and s.get('duration_months', 1) == 0
    )
    signals['high_endorse_zero_duration'] = high_endorse_zero_dur

    # ── Signal 6: Profile summary vs title disconnect ─────────────────────
    # (Lighter check — just flag clear disconnects)
    summary = profile.get('summary', '').lower()
    if is_non_tech and ('ranking system' in summary or 'retrieval' in summary
                        or 'ml infrastructure' in summary):
        signals['summary_title_disconnect'] = 1
    else:
        signals['summary_title_disconnect'] = 0

    # ── Signal 7: Employment starting before the company was founded ──────
    # This is the spec's own canonical honeypot example ("8 years of
    # experience at a company founded 3 years ago").
    max_founding_gap = 0
    for ch in career:
        founded = COMPANY_FOUNDED_YEAR.get(ch['company'].strip().lower())
        if founded:
            try:
                start_year = int(ch['start_date'][:4])
            except (TypeError, ValueError):
                continue
            gap = founded - start_year
            if gap > max_founding_gap:
                max_founding_gap = gap
    signals['founded_before_start'] = max_founding_gap

    # ── Signal 8: Stated experience exceeds the entire career timeline ────
    # years_of_experience cannot exceed the span from the earliest career
    # start date to today.
    earliest_start = None
    for ch in career:
        try:
            d = datetime.strptime(ch['start_date'], '%Y-%m-%d')
        except (TypeError, ValueError):
            continue
        if earliest_start is None or d < earliest_start:
            earliest_start = d
    if earliest_start is not None:
        span_years = (REFERENCE_DATE - earliest_start).days / 365.25
        excess = profile['years_of_experience'] - span_years
        signals['yoe_exceeds_span'] = excess if excess > 2.0 else 0
    else:
        signals['yoe_exceeds_span'] = 0

    # ── Signal 9: Summary text contradicts the years_of_experience field ──
    m = _SUMMARY_YEARS_RE.search(profile.get('summary', ''))
    if m:
        claimed = float(m.group(1))
        diff = abs(claimed - profile['years_of_experience'])
        signals['summary_yoe_mismatch'] = diff if diff > 3.0 else 0
    else:
        signals['summary_yoe_mismatch'] = 0

    return signals


def detect_honeypot(candidate: dict) -> float:
    """
    Returns a honeypot penalty multiplier (0-1).
    1.0 = definitely NOT a honeypot (no penalty)
    0.0 = definitely IS a honeypot (full penalty / exclude)
    """
    sigs = _compute_honeypot_signals(candidate)

    # Compute suspicion score
    suspicion = 0.0

    # Expert skills with 0 duration — strong honeypot signal
    if sigs['expert_zero_duration'] >= 5:
        suspicion += 5.0
    elif sigs['expert_zero_duration'] >= 3:
        suspicion += 3.0
    elif sigs['expert_zero_duration'] >= 2:
        suspicion += 1.5

    # All-expert with many skills
    if sigs['all_expert_many_skills'] >= 8:
        suspicion += 3.0
    elif sigs['all_expert_many_skills'] >= 5:
        suspicion += 1.5

    # Experience inflation
    if sigs['experience_inflation'] > 60:
        suspicion += 2.0
    elif sigs['experience_inflation'] > 36:
        suspicion += 1.0

    # Title-skill mismatch (non-tech title + deep ML skills)
    if sigs['title_skill_mismatch'] >= 7:
        suspicion += 3.0
    elif sigs['title_skill_mismatch'] >= 5:
        suspicion += 1.5

    # High endorsement with zero duration
    if sigs['high_endorse_zero_duration'] >= 3:
        suspicion += 2.0

    # Summary-title disconnect
    if sigs['summary_title_disconnect']:
        suspicion += 0.5

    # Employment predating company founding — hard impossibility.
    # A 1-year gap is within date-fuzziness tolerance; 2+ years is impossible.
    if sigs['founded_before_start'] >= 2:
        suspicion += 5.0
    elif sigs['founded_before_start'] == 1:
        suspicion += 1.0

    # Stated experience exceeds entire career timeline — hard impossibility
    if sigs['yoe_exceeds_span'] > 4:
        suspicion += 5.0
    elif sigs['yoe_exceeds_span'] > 0:
        suspicion += 3.0

    # Summary contradicts the years_of_experience field
    if sigs['summary_yoe_mismatch'] > 6:
        suspicion += 3.0
    elif sigs['summary_yoe_mismatch'] > 0:
        suspicion += 1.5

    # Map suspicion score to penalty
    if suspicion >= 5.0:
        return 0.0  # Almost certainly a honeypot — exclude
    elif suspicion >= 3.0:
        return 0.1  # Very likely honeypot
    elif suspicion >= 2.0:
        return 0.3  # Suspicious
    elif suspicion >= 1.0:
        return 0.6  # Mildly suspicious
    else:
        return 1.0  # Clean
