"""
Career Quality Scorer

Evaluates career history for signals the JD cares about:
1. Product company experience vs consulting-only
2. Relevant industry experience (Software, AI/ML, Fintech, etc.)
3. Career trajectory (growing into more senior ML roles)
4. Tenure patterns (title-chasers penalized)
5. Career description relevance (mentions ranking, retrieval, embeddings, etc.)

Key JD quotes:
- "People who have only worked at consulting firms... We've had bad fit experiences"
- "If your career trajectory shows you optimizing for titles by switching every 1.5 years"
- "Has shipped at least one end-to-end ranking, search, or recommendation system"
"""


# ── Company classifications ────────────────────────────────────────────────

CONSULTING_FIRMS = {
    'tcs', 'infosys', 'wipro', 'accenture', 'cognizant', 'capgemini',
    'hcl', 'tech mahindra', 'mindtree', 'mphasis', 'genpact ai',
}

PRODUCT_COMPANIES_TIER1 = {
    'google', 'meta', 'apple', 'microsoft', 'amazon', 'flipkart',
    'razorpay', 'cred', 'swiggy', 'zomato', 'meesho', 'adobe',
    'phonepe', 'paytm', 'dream11', 'freshworks', 'zoho', 'inmobi',
    'linkedin', 'netflix', 'salesforce', 'uber',
}

PRODUCT_COMPANIES_TIER2 = {
    'nykaa', 'ola', 'policybazaar', 'unacademy', 'vedantu', 'upgrad',
    'pharmeasy', "byju's", 'glance', 'haptik', 'niramai',
}

AI_COMPANIES = {
    'glance', 'aganitha', 'genpact ai', 'locobuzz', 'niramai',
    'mad street den', 'yellow.ai', 'haptik', 'sarvam ai',
    'verloop.io', 'krutrim',
}

# Fictional companies — treated as neutral
FICTIONAL_COMPANIES = {
    'pied piper', 'initech', 'wayne enterprises', 'acme corp',
    'stark industries', 'hooli', 'globex inc', 'dunder mifflin',
}

# Relevant industries
STRONG_INDUSTRIES = {'ai/ml', 'software', 'fintech', 'internet', 'saas', 'adtech',
                     'ai services', 'healthtech ai', 'conversational ai', 'voice ai',
                     'media', 'gaming'}
MODERATE_INDUSTRIES = {'e-commerce', 'edtech', 'food delivery', 'consumer electronics',
                       'healthtech', 'insurance tech', 'transportation'}
WEAK_INDUSTRIES = {'it services', 'consulting', 'conglomerate'}
IRRELEVANT_INDUSTRIES = {'manufacturing', 'paper products'}

# Keywords in career descriptions that signal relevant experience
CAREER_KEYWORDS_STRONG = [
    'ranking', 'retrieval', 'search', 'recommendation', 'embeddings',
    'vector', 'nlp', 'information retrieval', 'candidate matching',
    'bm25', 'faiss', 'ndcg', 'mrr', 'a/b test', 'recall', 'precision',
    'reranking', 're-ranking', 'machine learning', 'ml model',
    'deployed', 'production', 'real users', 'inference',
]

CAREER_KEYWORDS_MODERATE = [
    'deep learning', 'transformer', 'fine-tun', 'llm', 'bert',
    'pytorch', 'tensorflow', 'model training', 'pipeline',
    'feature engineering', 'data science', 'classification',
    'neural network', 'natural language', 'text',
]


def _normalize_company(name: str) -> str:
    return name.strip().lower()


def _industry_score(industry: str) -> float:
    ind = industry.strip().lower()
    if ind in STRONG_INDUSTRIES:
        return 1.0
    if ind in MODERATE_INDUSTRIES:
        return 0.75
    if ind in WEAK_INDUSTRIES:
        return 0.3
    if ind in IRRELEVANT_INDUSTRIES:
        return 0.1
    return 0.4


def _company_type_score(company: str) -> float:
    c = _normalize_company(company)
    if c in PRODUCT_COMPANIES_TIER1:
        return 1.0
    if c in PRODUCT_COMPANIES_TIER2 or c in AI_COMPANIES:
        return 0.9
    if c in CONSULTING_FIRMS:
        return 0.15
    if c in FICTIONAL_COMPANIES:
        return 0.45  # neutral — can't tell
    return 0.5


def _description_relevance(desc: str) -> float:
    """Score how relevant a career description is to the JD requirements."""
    desc_lower = desc.lower()
    strong_hits = sum(1 for kw in CAREER_KEYWORDS_STRONG if kw in desc_lower)
    moderate_hits = sum(1 for kw in CAREER_KEYWORDS_MODERATE if kw in desc_lower)

    # Weighted keyword density
    raw = strong_hits * 2.0 + moderate_hits * 1.0
    # Normalize: 0 hits → 0, ~8+ hits → 1.0
    return min(raw / 8.0, 1.0)


def score_career(candidate: dict) -> float:
    """
    Score career quality on a 0-1 scale.

    Sub-components:
    A) Company quality mix (product vs consulting)
    B) Industry relevance
    C) Career description relevance (mentions ranking/retrieval/etc)
    D) Tenure health (penalize title-chasers)
    E) All-consulting penalty
    """
    career = candidate['career_history']

    if not career:
        return 0.0

    total_months = sum(ch['duration_months'] for ch in career)
    if total_months == 0:
        total_months = 1

    # A) Weighted company quality (by duration)
    company_score = 0.0
    for ch in career:
        weight = ch['duration_months'] / total_months
        company_score += weight * _company_type_score(ch['company'])

    # B) Weighted industry relevance (by duration)
    industry_score = 0.0
    for ch in career:
        weight = ch['duration_months'] / total_months
        industry_score += weight * _industry_score(ch['industry'])

    # C) Career description relevance — best role matters most, plus profile summary/headline
    desc_scores = [_description_relevance(ch['description']) for ch in career]
    best_desc = max(desc_scores) if desc_scores else 0.0
    avg_desc = sum(desc_scores) / len(desc_scores) if desc_scores else 0.0
    
    profile_text = candidate['profile'].get('summary', '') + ' ' + candidate['profile'].get('headline', '')
    profile_desc_score = _description_relevance(profile_text)
    
    desc_relevance = 0.5 * best_desc + 0.3 * avg_desc + 0.2 * profile_desc_score

    # D) Tenure health — penalize frequent job-hopping
    num_roles = len(career)
    avg_tenure_months = total_months / num_roles
    if avg_tenure_months >= 30:
        tenure_score = 1.0
    elif avg_tenure_months >= 20:
        tenure_score = 0.8
    elif avg_tenure_months >= 14:
        tenure_score = 0.5
    else:
        tenure_score = 0.2  # Title-chaser territory

    # E) All-consulting penalty
    all_consulting = all(
        _normalize_company(ch['company']) in CONSULTING_FIRMS
        for ch in career
    )
    consulting_penalty = 0.25 if all_consulting else 1.0

    # Combine sub-scores
    raw = (
        0.25 * company_score +
        0.20 * industry_score +
        0.35 * desc_relevance +
        0.20 * tenure_score
    )

    # Apply all-consulting penalty
    final = raw * consulting_penalty

    return round(min(final, 1.0), 4)
