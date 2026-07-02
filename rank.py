#!/usr/bin/env python3
"""
Intelligent Candidate Discovery & Ranking System
================================================

Ranks 100K candidates against a Senior AI/ML Engineer job description
using a multi-signal weighted scoring system.

Architecture:
  1. Title & Role Fit (25%)  — Is this person in a relevant ML/AI role?
  2. Career Quality (25%)    — Product company experience, relevant work
  3. Skills Match (20%)      — Core JD skills coverage and quality
  4. Behavioral Signals (15%) — Active, responsive, available
  5. Experience Years (8%)    — 5-9 year sweet spot
  6. Location & Logistics (4%) — India, preferred cities
  7. Education (3%)           — Relevant field, institution tier

  × Honeypot Penalty         — Multiplier to filter impossible profiles

Usage:
  python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Constraints met:
  - ≤ 5 minutes wall-clock on CPU
  - ≤ 16 GB RAM
  - No GPU
  - No network calls
"""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

# ── Scoring modules ─────────────────────────────────────────────────────────
from scoring.title_scorer import score_title
from scoring.career_scorer import score_career
from scoring.skills_scorer import score_skills
from scoring.behavioral_scorer import score_behavioral
from scoring.experience_scorer import score_experience
from scoring.location_scorer import score_location
from scoring.education_scorer import score_education
from scoring.honeypot_detector import detect_honeypot
from scoring.reasoning_generator import generate_reasoning

# ── Component weights ───────────────────────────────────────────────────────
WEIGHTS = {
    'title':      0.25,
    'career':     0.25,
    'skills':     0.20,
    'behavioral': 0.15,
    'experience': 0.08,
    'location':   0.04,
    'education':  0.03,
}

TOP_K = 100


def compute_composite_score(candidate: dict) -> tuple:
    """
    Compute the final composite score for a candidate.

    Returns:
        (final_score, score_breakdown_dict)
    """
    breakdown = {
        'title':      score_title(candidate),
        'career':     score_career(candidate),
        'skills':     score_skills(candidate),
        'behavioral': score_behavioral(candidate),
        'experience': score_experience(candidate),
        'location':   score_location(candidate),
        'education':  score_education(candidate),
    }

    # Weighted sum
    raw_score = sum(
        WEIGHTS[component] * breakdown[component]
        for component in WEIGHTS
    )

    # Apply honeypot penalty
    honeypot_multiplier = detect_honeypot(candidate)
    breakdown['honeypot'] = honeypot_multiplier

    final_score = raw_score * honeypot_multiplier

    return final_score, breakdown


def rank_candidates(candidates_path: str, output_path: str):
    """
    Main ranking pipeline.

    Reads candidates from JSONL, scores each, selects top-100,
    generates reasoning, and writes submission CSV.
    """
    start_time = time.time()

    print(f"[1/5] Loading candidates from {candidates_path}...")
    scored = []
    total = 0
    honeypots_detected = 0

    with open(candidates_path, 'r', encoding='utf-8') as f:
        for line in f:
            candidate = json.loads(line)
            total += 1

            score, breakdown = compute_composite_score(candidate)

            if breakdown['honeypot'] < 0.5:
                honeypots_detected += 1

            scored.append((
                score,
                candidate['candidate_id'],
                breakdown,
                candidate,
            ))

            if total % 10000 == 0:
                elapsed = time.time() - start_time
                print(f"  Processed {total:,} candidates ({elapsed:.1f}s)")

    elapsed = time.time() - start_time
    print(f"[2/5] Scored {total:,} candidates in {elapsed:.1f}s")
    print(f"  Honeypots detected: {honeypots_detected}")

    # Sort by score descending, then candidate_id ascending for tiebreaking
    print("[3/5] Sorting and selecting top-100...")
    scored.sort(key=lambda x: (-x[0], x[1]))
    top_100 = scored[:TOP_K]

    # Re-sort to satisfy the validator's tie-break rule on ROUNDED scores:
    # Equal displayed scores must have candidate_id ascending.
    # We sort by (-rounded_score, candidate_id) to ensure this.
    top_100_with_rounded = []
    for score, cand_id, breakdown, candidate in top_100:
        score_rounded = round(score, 4)
        top_100_with_rounded.append((score_rounded, cand_id, breakdown, candidate))

    top_100_with_rounded.sort(key=lambda x: (-x[0], x[1]))

    # Generate reasoning for top-100
    print("[4/5] Generating reasoning for top-100...")
    rows = []
    for rank_idx, (score_rounded, cand_id, breakdown, candidate) in enumerate(top_100_with_rounded):
        rank = rank_idx + 1
        reasoning = generate_reasoning(candidate, rank, breakdown)

        rows.append({
            'candidate_id': cand_id,
            'rank': rank,
            'score': f"{score_rounded:.4f}",
            'reasoning': reasoning,
        })

    # Write CSV
    print(f"[5/5] Writing submission to {output_path}...")
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['candidate_id', 'rank', 'score', 'reasoning'])
        writer.writeheader()
        writer.writerows(rows)

    total_time = time.time() - start_time
    print(f"\nDone! Ranked {total:,} candidates in {total_time:.1f}s")
    print(f"Top-100 written to {output_path}")
    print(f"\nTop-10 preview:")
    for row in rows[:10]:
        print(f"  Rank {row['rank']:>3}: {row['candidate_id']}  "
              f"score={row['score']}  {row['reasoning'][:80]}...")

    return rows


def main():
    parser = argparse.ArgumentParser(
        description='Intelligent Candidate Discovery & Ranking System'
    )
    parser.add_argument(
        '--candidates', default='./candidates.jsonl',
        help='Path to candidates JSONL file'
    )
    parser.add_argument(
        '--out', default='./submission.csv',
        help='Output CSV file path'
    )
    args = parser.parse_args()

    if not Path(args.candidates).exists():
        print(f"Error: Candidates file not found: {args.candidates}")
        sys.exit(1)

    rank_candidates(args.candidates, args.out)


if __name__ == '__main__':
    main()
