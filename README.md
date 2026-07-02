---
title: Redrob Ranker
emoji: 🔍
colorFrom: blue
colorTo: gray
sdk: streamlit
sdk_version: 1.35.0
app_file: app.py
pinned: false
---

# Intelligent Candidate Discovery & Ranking System

Rule-based, deterministic ranker for the Redrob "Intelligent Candidate Discovery & Ranking Challenge". Reads 100,000 candidate profiles, scores them against the Senior AI/ML Engineer JD, and outputs the top-100 as a submission CSV — in ~10 seconds on CPU with zero external dependencies.

## Reproduce the submission

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

That single command produces `submission.csv` from the candidates file. There is no pre-computation step, no model download, no network access, and no GPU.

Validate before uploading:

```bash
python validate_submission.py submission.csv
```

### Requirements

- Python 3.11+ (standard library only — see `requirements.txt`)
- `candidates.jsonl` from the hackathon bundle placed in the repo root (it is `.gitignore`d due to size; `gunzip -k candidates.jsonl.gz` if you have the gzipped bundle)

### Measured performance (MacBook Pro, CPU only)

| Constraint | Limit | Measured |
|---|---|---|
| Runtime | ≤ 5 min | **~10 s** |
| Memory | ≤ 16 GB | **~1.8 GB peak** |
| GPU | none allowed | none used |
| Network | none allowed | none used |
| Disk intermediate state | ≤ 5 GB | 0 (streams input, writes only the CSV) |

## Architecture

The JD explicitly warns: *"The right answer is NOT find candidates whose skills section contains the most AI keywords. That's a trap."*

So this system does not embed-and-cosine its way through the pool. It encodes the JD's actual hiring rubric as 7 independently designed scoring dimensions, combined as a weighted sum, then multiplied by a honeypot penalty:

```
score = (0.25·title + 0.25·career + 0.20·skills + 0.15·behavioral
         + 0.08·experience + 0.04·location + 0.03·education) × honeypot_multiplier
```

| Component | Weight | What it captures |
|-----------|--------|-----------------|
| **Title & role fit** (`title_scorer.py`) | 25% | 5-tier title classification, from direct match (Staff ML Engineer, Search Engineer, Recommendation Systems Engineer) down to non-technical (Marketing Manager → 0). Blends current title (70%) with best historical title (30%). |
| **Career quality** (`career_scorer.py`) | 25% | Product company vs consulting (all-consulting careers get a 0.25× penalty, per the JD's explicit disqualifier), industry relevance, JD-keyword analysis of role descriptions (ranking, retrieval, embeddings, NDCG…), tenure health (job-hopper penalty below 14-month average tenure). |
| **Skills match** (`skills_scorer.py`) | 20% | Must-have JD skills (embeddings, vector DBs, Python, ranking eval) weighted by proficiency × duration_months — so "expert with 0 months" is worth nothing. Wrong-domain (CV/speech/robotics-only) penalty. Redrob skill-assessment scores. Keyword-stuffing penalty. |
| **Behavioral signals** (`behavioral_scorer.py`) | 15% | Platform recency, recruiter response rate and speed, open-to-work + notice period, profile completeness/verification, market demand (saved by recruiters, profile views, GitHub activity), interview/offer reliability. |
| **Experience years** (`experience_scorer.py`) | 8% | Bell curve over the JD's 5–9 year band, peaking at 5.5–8.5. |
| **Location & logistics** (`location_scorer.py`) | 4% | India strongly preferred (no visa sponsorship), Pune/Noida then metro cities, work-mode fit, relocation willingness, salary-band sanity. |
| **Education** (`education_scorer.py`) | 3% | Field relevance (CS/ML/DS), institution tier, degree level. Deliberately a weak signal. |

### Honeypot detection (`honeypot_detector.py`)

The dataset contains ~80 honeypots with subtly impossible profiles, and >10% of them in the top-100 means disqualification. Detection is multi-signal; hard impossibilities zero the candidate out entirely:

1. **Employment predating company founding** — the spec's own canonical example ("8 years at a company founded 3 years ago"). Checked against a public-knowledge founding-year table for the real companies in the dataset (Krutrim 2023, Sarvam AI 2023, Glance 2019, …). A 2+ year gap is treated as impossible.
2. **Stated `years_of_experience` exceeding the entire career timeline** (earliest start date → today).
3. **Profile summary contradicting the experience field** (e.g. summary says "8.3 years", field says 16.2).
4. **"Expert" skills with 0 duration months**, especially with high endorsement counts.
5. **Mass all-expert skill lists** with near-zero average duration.
6. **Non-technical titles with deep ML skill stacks** (the keyword-stuffer archetype).

Suspicion is accumulated across signals and mapped to a multiplier (1.0 clean → 0.0 exclude). Audit of the final top-100: **0 candidates with any impossibility flag**.

### Reasoning generation (`reasoning_generator.py`)

Every top-100 row gets reasoning assembled **only from facts present in that candidate's profile** (no hallucination risk by construction): current role and company, years of experience, actual JD-matching skills from their skill list, career trajectory, education tier, behavioral signals — plus honest, rank-appropriate concerns (long notice period, low response rate, non-India location, skill-coverage gaps). All 100 strings are unique and non-templated.

### Tie-breaking

Scores are rounded to 4 decimals for output, then the top-100 is re-sorted by `(-rounded_score, candidate_id)` so that equal displayed scores are always in candidate_id-ascending order — exactly what `validate_submission.py` enforces.

## Project structure

```
rank.py                     # Entry point: stream → score → sort → top-100 → CSV
scoring/
  title_scorer.py           # 5-tier title classification
  career_scorer.py          # Company/industry/description/tenure analysis
  skills_scorer.py          # Quality-over-quantity skill matching
  behavioral_scorer.py      # Redrob platform signals
  experience_scorer.py      # 5-9 year bell curve
  location_scorer.py        # Geography + logistics
  education_scorer.py       # Field/tier/degree
  honeypot_detector.py      # Impossible-profile detection
  reasoning_generator.py    # Fact-grounded per-candidate reasoning
validate_submission.py      # Official validator (from hackathon bundle)
submission.csv              # Generated top-100 ranking
submission_metadata.yaml    # Portal metadata mirror
requirements.txt            # Empty on purpose — stdlib only
```

## Results snapshot (final top-100)

- 100/100 hold ML/AI/search/recommendation titles (Applied ML Engineer, Recommendation Systems Engineer, Search Engineer, ML Engineer, …)
- 94/100 based in India
- 86/100 inside the 5–9 year experience band (range 4.1–9.0)
- 0 honeypot / impossible profiles (independently re-audited post-run)
- 0 consulting-only careers
- 100/100 unique, fact-grounded reasoning strings

## Design philosophy

1. **Title is king** — the JD says a Marketing Manager with every AI keyword is not a fit. Title + career = 50% of the score.
2. **Quality over quantity** — skills score on proficiency × actual duration, which neutralizes keyword stuffing without special-casing it.
3. **Hireability matters** — a perfect resume that never responds to recruiters is down-weighted, exactly as the signals doc instructs.
4. **Determinism** — no randomness, no LLM calls, no network. Same input → same output, every run.
