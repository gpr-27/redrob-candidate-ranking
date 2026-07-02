"""
Skills Match Scorer

Evaluates how well a candidate's skills match the JD requirements.

JD explicitly calls out:
  MUST-HAVE:
    - Production embeddings-based retrieval (sentence-transformers, BGE, E5, etc.)
    - Vector databases (Pinecone, Weaviate, Qdrant, Milvus, FAISS, OpenSearch, ES)
    - Strong Python
    - Evaluation frameworks (NDCG, MRR, MAP)

  NICE-TO-HAVE:
    - LLM fine-tuning (LoRA, QLoRA, PEFT)
    - Learning-to-rank (XGBoost-based or neural)
    - HR-tech / marketplace exposure
    - Distributed systems / large-scale inference

  DO-NOT-WANT signals:
    - CV/speech/robotics without NLP/IR
    - Framework enthusiasts (LangChain tutorials only)

The JD also warns: "The right answer is NOT find candidates whose skills section
contains the most AI keywords. That's a trap."

So we need to value QUALITY over QUANTITY of skills, and trust proficiency
+ endorsements + duration over just the skill name.
"""


# ── Skill categorization ──────────────────────────────────────────────────

# Must-have skills (per JD "Things you absolutely need")
MUST_HAVE_SKILLS = {
    # Embeddings-based retrieval
    'sentence transformers', 'embeddings', 'hugging face transformers',
    'vector search', 'semantic search', 'information retrieval',
    'information retrieval systems',
    # Vector databases
    'pinecone', 'weaviate', 'qdrant', 'milvus', 'faiss', 'opensearch',
    'elasticsearch', 'pgvector',
    # Python
    'python',
    # Evaluation / Ranking
    'learning to rank', 'ranking systems', 'bm25',
    # Search/Recommendation systems
    'recommendation systems', 'search & discovery', 'search backend',
    'search infrastructure',
}

# High-value ML skills (closely aligned with the role)
HIGH_VALUE_SKILLS = {
    'nlp', 'natural language processing', 'deep learning',
    'machine learning', 'pytorch', 'tensorflow', 'scikit-learn',
    'rag', 'langchain', 'llamaindex', 'haystack',
    'fine-tuning llms', 'llms', 'prompt engineering',
    'text encoders', 'content matching', 'vector representations',
    'data science', 'feature engineering', 'statistical modeling',
    'mlops', 'mlflow', 'kubeflow', 'bentoml', 'weights & biases',
}

# Nice-to-have skills (per JD)
NICE_TO_HAVE_SKILLS = {
    'lora', 'qlora', 'peft', 'model adaptation',
    'indexing algorithms', 'open-source ml libraries',
    'workflow orchestration',
}

# Good technical skills (general SWE that show coding ability)
GOOD_TECH_SKILLS = {
    'docker', 'kubernetes', 'fastapi', 'flask', 'django',
    'rest apis', 'grpc', 'microservices', 'ci/cd',
    'spark', 'airflow', 'data pipelines', 'kafka',
    'sql', 'postgresql', 'mongodb', 'redis',
    'aws', 'gcp', 'azure', 'databricks', 'snowflake',
    'go', 'rust', 'java',
}

# Skills that signal WRONG domain (per JD "do not want")
WRONG_DOMAIN_SKILLS = {
    'yolo', 'opencv', 'image classification', 'object detection',
    'computer vision', 'cnn', 'diffusion models', 'gans',
    'speech recognition', 'asr', 'tts',
    'reinforcement learning',
}

# Non-technical skills (signal non-fit)
NON_TECH_SKILLS = {
    'project management', 'agile', 'scrum', 'six sigma',
    'marketing', 'seo', 'content writing', 'sales',
    'accounting', 'tally', 'sap', 'salesforce crm',
    'excel', 'powerpoint', 'photoshop', 'illustrator', 'figma',
}

# Proficiency scoring
PROFICIENCY_WEIGHTS = {
    'expert': 1.0,
    'advanced': 0.75,
    'intermediate': 0.45,
    'beginner': 0.2,
}


def _normalize_skill(name: str) -> str:
    return name.strip().lower()


def score_skills(candidate: dict) -> float:
    """
    Score skills match on a 0-1 scale.

    Sub-components:
    A) Must-have skill coverage (most important)
    B) High-value ML skill quality
    C) Nice-to-have bonus
    D) Wrong-domain penalty
    E) Skill assessment scores from Redrob platform
    F) Keyword stuffing detection
    """
    skills = candidate['skills']
    signals = candidate['redrob_signals']

    if not skills:
        return 0.0

    # Build skill lookup
    skill_map = {}
    for s in skills:
        name = _normalize_skill(s['name'])
        skill_map[name] = s

    # A) Must-have skill coverage
    must_have_hits = 0
    must_have_quality = 0.0
    for skill_name in MUST_HAVE_SKILLS:
        if skill_name in skill_map:
            s = skill_map[skill_name]
            must_have_hits += 1
            prof = PROFICIENCY_WEIGHTS.get(s['proficiency'], 0.3)
            duration_factor = min(s.get('duration_months', 0) / 24.0, 1.0)
            # Quality = proficiency × duration factor
            must_have_quality += prof * (0.5 + 0.5 * duration_factor)

    # Normalize: having 5+ must-have skills with quality → 1.0
    must_have_score = min(must_have_quality / 4.0, 1.0)

    # B) High-value ML skills
    high_value_hits = 0
    high_value_quality = 0.0
    for skill_name in HIGH_VALUE_SKILLS:
        if skill_name in skill_map:
            s = skill_map[skill_name]
            high_value_hits += 1
            prof = PROFICIENCY_WEIGHTS.get(s['proficiency'], 0.3)
            high_value_quality += prof

    high_value_score = min(high_value_quality / 5.0, 1.0)

    # C) Nice-to-have bonus
    nice_hits = sum(1 for s in NICE_TO_HAVE_SKILLS if s in skill_map)
    nice_score = min(nice_hits / 2.0, 1.0)

    # D) Wrong-domain ratio — penalize if most skills are CV/speech
    wrong_domain_count = sum(1 for s in skill_map if s in WRONG_DOMAIN_SKILLS)
    right_domain_count = sum(1 for s in skill_map
                            if s in MUST_HAVE_SKILLS or s in HIGH_VALUE_SKILLS)
    # Only penalize if wrong domain dominates
    if right_domain_count == 0 and wrong_domain_count >= 3:
        wrong_penalty = 0.5
    elif wrong_domain_count > right_domain_count * 2:
        wrong_penalty = 0.7
    else:
        wrong_penalty = 1.0

    # E) Skill assessment scores from Redrob platform
    assessments = signals.get('skill_assessment_scores', {})
    assessment_score = 0.0
    if assessments:
        relevant_assessment_scores = []
        for skill_name, score_val in assessments.items():
            s_lower = _normalize_skill(skill_name)
            # Weight relevant assessments higher
            if s_lower in MUST_HAVE_SKILLS or s_lower in HIGH_VALUE_SKILLS:
                relevant_assessment_scores.append(score_val * 1.5)
            else:
                relevant_assessment_scores.append(score_val)

        if relevant_assessment_scores:
            assessment_score = min(
                sum(relevant_assessment_scores) / (len(relevant_assessment_scores) * 100),
                1.0
            )

    # F) Keyword stuffing detection
    # Expert proficiency with 0 duration is suspicious
    expert_zero_duration = sum(
        1 for s in skills
        if s['proficiency'] == 'expert' and s.get('duration_months', 1) == 0
    )
    stuffing_penalty = 1.0
    if expert_zero_duration >= 3:
        stuffing_penalty = 0.3
    elif expert_zero_duration >= 2:
        stuffing_penalty = 0.6

    # Non-technical skill ratio
    non_tech_count = sum(1 for s in skill_map if s in NON_TECH_SKILLS)
    total_skills = len(skill_map)
    non_tech_ratio = non_tech_count / total_skills if total_skills > 0 else 0

    # Combine sub-scores
    raw = (
        0.40 * must_have_score +
        0.25 * high_value_score +
        0.10 * nice_score +
        0.15 * assessment_score +
        0.10 * (1.0 - non_tech_ratio)
    )

    # Apply penalties
    final = raw * wrong_penalty * stuffing_penalty

    return round(min(final, 1.0), 4)
