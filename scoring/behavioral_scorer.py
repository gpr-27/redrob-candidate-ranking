"""
Behavioral Signals Scorer

Evaluates Redrob platform engagement and availability signals.

Key JD guidance:
- "A perfect-on-paper candidate who hasn't logged in for 6 months and has a
   5% recruiter response rate is, for hiring purposes, not actually available.
   Down-weight them appropriately."
- "Notice period: We'd love sub-30-day notice. 30+ day notice candidates
   are still in scope but the bar gets higher."
- "Active on Redrob platform"

This scorer captures AVAILABILITY and ENGAGEMENT — whether the candidate
can actually be hired, not just whether they look good on paper.
"""

from datetime import datetime, date

# Reference date for computing recency (dataset snapshot date)
REFERENCE_DATE = date(2026, 6, 1)


def _days_since(date_str: str) -> int:
    """Return days between date_str and reference date."""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        delta = (REFERENCE_DATE - d).days
        return max(delta, 0)
    except (ValueError, TypeError):
        return 365  # assume stale if can't parse


def score_behavioral(candidate: dict) -> float:
    """
    Score behavioral/engagement signals on a 0-1 scale.

    Sub-components:
    A) Recency — how recently active on platform
    B) Responsiveness — recruiter response rate + response time
    C) Availability — open to work, notice period
    D) Profile quality — completeness, verifications
    E) Market signal — searched/saved by recruiters, GitHub
    F) Hiring reliability — interview completion, offer acceptance
    """
    signals = candidate['redrob_signals']

    # A) Recency: last active date
    days_inactive = _days_since(signals['last_active_date'])
    if days_inactive <= 7:
        recency_score = 1.0
    elif days_inactive <= 30:
        recency_score = 0.9
    elif days_inactive <= 90:
        recency_score = 0.7
    elif days_inactive <= 180:
        recency_score = 0.4
    elif days_inactive <= 365:
        recency_score = 0.15
    else:
        recency_score = 0.05

    # B) Responsiveness
    response_rate = signals['recruiter_response_rate']
    response_time = signals['avg_response_time_hours']

    # Response rate: higher is much better
    if response_rate >= 0.7:
        resp_rate_score = 1.0
    elif response_rate >= 0.5:
        resp_rate_score = 0.8
    elif response_rate >= 0.3:
        resp_rate_score = 0.5
    elif response_rate >= 0.15:
        resp_rate_score = 0.3
    else:
        resp_rate_score = 0.1

    # Response time: faster is better
    if response_time <= 12:
        resp_time_score = 1.0
    elif response_time <= 24:
        resp_time_score = 0.9
    elif response_time <= 48:
        resp_time_score = 0.7
    elif response_time <= 96:
        resp_time_score = 0.5
    elif response_time <= 168:
        resp_time_score = 0.3
    else:
        resp_time_score = 0.1

    responsiveness = 0.65 * resp_rate_score + 0.35 * resp_time_score

    # C) Availability
    open_to_work = signals['open_to_work_flag']
    notice_days = signals['notice_period_days']

    if notice_days <= 15:
        notice_score = 1.0
    elif notice_days <= 30:
        notice_score = 0.9
    elif notice_days <= 60:
        notice_score = 0.65
    elif notice_days <= 90:
        notice_score = 0.4
    else:
        notice_score = 0.2

    availability = 0.4 * (1.0 if open_to_work else 0.3) + 0.6 * notice_score

    # D) Profile quality
    completeness = signals['profile_completeness_score'] / 100.0
    verified = (
        (0.4 if signals['verified_email'] else 0.0) +
        (0.3 if signals['verified_phone'] else 0.0) +
        (0.3 if signals['linkedin_connected'] else 0.0)
    )
    profile_quality = 0.6 * completeness + 0.4 * verified

    # E) Market signals — how the market sees this candidate
    saved = signals['saved_by_recruiters_30d']
    views = signals['profile_views_received_30d']
    github = signals['github_activity_score']

    # Saved by recruiters
    if saved >= 10:
        saved_score = 1.0
    elif saved >= 5:
        saved_score = 0.7
    elif saved >= 2:
        saved_score = 0.4
    else:
        saved_score = 0.15

    # Profile views
    if views >= 20:
        views_score = 1.0
    elif views >= 10:
        views_score = 0.7
    elif views >= 5:
        views_score = 0.4
    else:
        views_score = 0.15

    # GitHub activity (-1 means no GitHub)
    if github < 0:
        github_score = 0.2  # mild penalty for no GitHub
    elif github >= 70:
        github_score = 1.0
    elif github >= 40:
        github_score = 0.7
    elif github >= 15:
        github_score = 0.4
    else:
        github_score = 0.2

    market_signal = 0.30 * saved_score + 0.30 * views_score + 0.40 * github_score

    # F) Hiring reliability
    interview_rate = signals['interview_completion_rate']
    offer_rate = signals['offer_acceptance_rate']

    interview_score = interview_rate  # 0-1 directly

    if offer_rate < 0:
        offer_score = 0.4  # no history — neutral
    else:
        offer_score = offer_rate

    reliability = 0.6 * interview_score + 0.4 * offer_score

    # Combine all sub-scores
    final = (
        0.25 * recency_score +
        0.25 * responsiveness +
        0.15 * availability +
        0.10 * profile_quality +
        0.15 * market_signal +
        0.10 * reliability
    )

    return round(min(final, 1.0), 4)
