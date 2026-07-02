"""
Reasoning Generator

Generates specific, honest, per-candidate reasoning for the submission.

Stage 4 evaluation checks:
1. Specific facts from candidate profile (years, title, skills, signals)
2. Connection to specific JD requirements
3. Honest concerns where candidate has gaps
4. No hallucination — every claim matches the actual profile
5. Variation — not templated
6. Rank consistency — tone matches rank position
"""


def generate_reasoning(candidate: dict, rank: int, score_breakdown: dict) -> str:
    """
    Generate a concise, specific reasoning string for this candidate's ranking.

    Args:
        candidate: Full candidate dict
        rank: 1-100 ranking position
        score_breakdown: Dict with sub-scores for each component
    """
    profile = candidate['profile']
    signals = candidate['redrob_signals']
    skills = candidate['skills']
    career = candidate['career_history']
    education = candidate.get('education', [])

    # Extract key facts
    title = profile['current_title']
    company = profile['current_company']
    yoe = profile['years_of_experience']
    location = profile['location']
    country = profile['country']
    industry = profile['current_industry']

    # Key skills (top relevant ones)
    skill_names = [s['name'] for s in skills]

    # JD-relevant skills
    jd_core = {'Python', 'PyTorch', 'TensorFlow', 'scikit-learn', 'NLP',
                'Machine Learning', 'Deep Learning', 'Embeddings',
                'Sentence Transformers', 'FAISS', 'Pinecone', 'Weaviate',
                'Qdrant', 'Milvus', 'OpenSearch', 'Elasticsearch',
                'Vector Search', 'Semantic Search', 'RAG', 'LLMs',
                'Recommendation Systems', 'Learning to Rank', 'BM25',
                'Information Retrieval', 'Fine-tuning LLMs', 'LoRA',
                'QLoRA', 'PEFT', 'Haystack', 'LangChain', 'LlamaIndex',
                'Ranking Systems', 'Search & Discovery', 'pgvector',
                'MLOps', 'MLflow', 'Kubeflow', 'Feature Engineering',
                'Data Science', 'Prompt Engineering', 'Hugging Face Transformers',
                'Information Retrieval Systems', 'Search Backend',
                'Natural Language Processing'}

    matching_jd_skills = [s for s in skill_names if s in jd_core]
    non_matching_skills = [s for s in skill_names if s not in jd_core]

    # Behavioral signals
    response_rate = signals['recruiter_response_rate']
    last_active = signals['last_active_date']
    notice_days = signals['notice_period_days']
    open_to_work = signals['open_to_work_flag']
    github = signals['github_activity_score']

    # Career companies
    companies_worked = [ch['company'] for ch in career]
    titles_held = [ch['title'] for ch in career]

    # Build reasoning parts
    parts = []

    # ── Strengths (always mention for top candidates) ────────────────────
    # Title/role relevance
    if score_breakdown.get('title', 0) >= 0.7:
        parts.append(f"{title} at {company} ({industry})")
    else:
        parts.append(f"Currently {title} at {company}")

    # Experience
    parts.append(f"{yoe} yrs experience")

    # Key JD-matching skills (most important)
    if matching_jd_skills:
        top_skills = matching_jd_skills[:5]
        parts.append(f"JD-relevant skills: {', '.join(top_skills)}")

    # Career trajectory
    if len(career) > 1:
        career_summary = f"Career: {' → '.join(titles_held[:3])}"
        if len(career) > 3:
            career_summary += f" (+{len(career)-3} more roles)"
        parts.append(career_summary)

    # Education (if notable)
    if education:
        best_edu = education[0]
        if best_edu.get('tier') in ('tier_1', 'tier_2'):
            parts.append(f"{best_edu['degree']} {best_edu['field_of_study']} from {best_edu['institution']} ({best_edu['tier']})")

    # Location
    parts.append(f"Based in {location}, {country}")

    # ── Behavioral signals ──────────────────────────────────────────────
    behavioral_notes = []
    if open_to_work:
        behavioral_notes.append("open to work")
    if response_rate >= 0.6:
        behavioral_notes.append(f"high response rate ({response_rate:.0%})")
    elif response_rate <= 0.2:
        behavioral_notes.append(f"low response rate ({response_rate:.0%})")
    if github >= 50:
        behavioral_notes.append(f"active GitHub (score: {github})")
    if notice_days <= 30:
        behavioral_notes.append(f"{notice_days}d notice")
    elif notice_days >= 90:
        behavioral_notes.append(f"long notice period ({notice_days}d)")

    if behavioral_notes:
        parts.append("Signals: " + "; ".join(behavioral_notes))

    # ── Concerns / Gaps (honest, rank-appropriate) ───────────────────────
    concerns = []

    if rank <= 20:
        # For top candidates, mention minor concerns only
        if country != 'India':
            concerns.append(f"based outside India ({country}) — visa not sponsored")
        if notice_days > 60:
            concerns.append(f"notice period {notice_days}d exceeds preferred <30d")
    else:
        # For lower-ranked, be more explicit about gaps
        if not matching_jd_skills:
            concerns.append("no JD-core skills (embeddings, vector DBs, ranking)")
        elif len(matching_jd_skills) < 3:
            concerns.append(f"limited JD skill coverage ({len(matching_jd_skills)} matches)")

        if score_breakdown.get('title', 0) < 0.3:
            concerns.append(f"title ({title}) not aligned with ML/AI engineering role")

        if score_breakdown.get('career', 0) < 0.3:
            consulting = {'TCS', 'Infosys', 'Wipro', 'Accenture', 'Cognizant',
                         'Capgemini', 'HCL', 'Tech Mahindra', 'Mindtree', 'Mphasis'}
            career_consulting = [c for c in companies_worked if c in consulting]
            if len(career_consulting) == len(companies_worked):
                concerns.append("entire career at consulting firms")

        if country != 'India':
            concerns.append(f"based in {country} — no visa sponsorship")

        if response_rate < 0.2:
            concerns.append(f"very low recruiter response rate ({response_rate:.0%})")

        if yoe < 3:
            concerns.append(f"only {yoe} yrs — below JD's 5-9yr band")
        elif yoe > 12:
            concerns.append(f"{yoe} yrs — above JD's 5-9yr band")

    if concerns:
        parts.append("Concerns: " + "; ".join(concerns[:3]))

    # Keep under ~450 chars by dropping whole trailing segments rather than
    # cutting mid-sentence (Stage 4 reviewers read these).
    # The concerns segment (last, if present) is always kept.
    reasoning = ". ".join(parts) + "."
    while len(reasoning) > 450 and len(parts) > 2:
        concerns_part = parts.pop() if parts[-1].startswith("Concerns: ") else None
        parts.pop()  # drop the least important remaining detail
        if concerns_part:
            parts.append(concerns_part)
        reasoning = ". ".join(parts) + "."

    return reasoning
