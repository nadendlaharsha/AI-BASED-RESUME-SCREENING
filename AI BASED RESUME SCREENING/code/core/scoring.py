"""
Scoring Module

This module calculates various scores (semantic, skill, experience) for candidate
resumes against job descriptions. It aggregates these into a final score
and provides a confidence metric.
"""

from typing import List, Dict, Set, Optional, Any
from core.config import (
    SEMANTIC_WEIGHT,
    SKILL_WEIGHT,
    EXPERIENCE_WEIGHT,
    MUST_HAVE_PENALTY_MAX,
    EXPERIENCE_PENALTY_PER_YEAR,
    EXPERIENCE_PENALTY_MAX,
    SEMANTIC_PENALTY_THRESHOLD,
    SEMANTIC_PENALTY_VALUE,
    TOTAL_PENALTY_MAX,
)

# Default qualification weight — can be overridden via custom_weights
QUALIFICATION_WEIGHT = 0.15

def _normalize_set(items: Optional[List[str]]) -> Set[str]:
    """Normalize a list of strings into a set of lowercase strings."""
    if items is None:
        return set()
    return {s.strip().lower() for s in items if s and s.strip()}

def _find_original(matched_lower: Set[str], original_list: List[str]) -> List[str]:
    """Recover original case formatting for matched lowercase strings."""
    if not matched_lower or not original_list:
        return []
    return [s for s in original_list if s and s.strip().lower() in matched_lower]

def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value between a minimum and maximum."""
    return max(min_val, min(max_val, float(value)))

def _compute_confidence(resume_text_len: int, skills_found: int,
                        has_experience: bool) -> float:
    """
    Compute a confidence score for the parsing quality based on
    text length, skills found, and experience detection.
    """
    confidence = 0.0

    if resume_text_len >= 1000:
        confidence += 0.4
    elif resume_text_len >= 500:
        confidence += 0.3
    elif resume_text_len >= 200:
        confidence += 0.2
    else:
        confidence += 0.1

    if skills_found >= 5:
        confidence += 0.35
    elif skills_found >= 3:
        confidence += 0.25
    elif skills_found >= 1:
        confidence += 0.15
    else:
        confidence += 0.05

    if has_experience:
        confidence += 0.25
    else:
        confidence += 0.1

    return _clamp(confidence)

def compute_experience_score(candidate_experience: float,
                             required_experience: float) -> float:
    """
    Calculate score based on years of experience vs required.
    Uses a non-linear scale: 
    - 0 to required: linear ratio (0.0 to 1.0)
    - Beyond required: small bonus (up to +0.1) for extra seniority.
    """
    candidate_exp = max(0.0, float(candidate_experience) if candidate_experience else 0.0)
    required_exp = max(0.0, float(required_experience) if required_experience else 0.0)

    if required_exp <= 0:
        # When experience is not mandatory, keep this as a soft-fit metric
        # instead of hard 100% to avoid over-inflating candidate cards.
        if candidate_exp <= 0:
            return 0.65
        if candidate_exp < 1:
            return 0.75
        if candidate_exp < 2:
            return 0.85
        return 0.9

    if candidate_exp >= required_exp:
        # Cap at 1.0, no bonus for extra experience
        return 1.0
    
    # Linear ratio for candidates below requirement
    return _clamp(candidate_exp / required_exp)

def _compute_additional_penalty(missing_must_count: int,
                                total_must_count: int,
                                candidate_experience: float,
                                required_experience: float,
                                semantic_score: float) -> Dict[str, float]:
    """
    Compute explicit modern penalties without modifying the core weighted formula.
    This penalty layer is applied after base score + alignment factor.
    """
    missing_must_count = max(0, int(missing_must_count or 0))
    total_must_count = max(0, int(total_must_count or 0))
    candidate_experience = max(0.0, float(candidate_experience or 0.0))
    required_experience = max(0.0, float(required_experience or 0.0))
    semantic_score = _clamp(float(semantic_score or 0.0))

    # Role-size-aware must-have penalty.
    # Max 16% only when all must-have skills are missing.
    missing_must_ratio = (missing_must_count / total_must_count) if total_must_count > 0 else 0.0
    must_have_penalty = min(
        _clamp(float(MUST_HAVE_PENALTY_MAX), 0.0, 1.0),
        _clamp(float(MUST_HAVE_PENALTY_MAX), 0.0, 1.0) * missing_must_ratio
    )

    # 2% penalty per missing experience year when experience is required.
    experience_gap = max(0.0, required_experience - candidate_experience)
    experience_gap_penalty = (
        min(
            _clamp(float(EXPERIENCE_PENALTY_MAX), 0.0, 1.0),
            experience_gap * _clamp(float(EXPERIENCE_PENALTY_PER_YEAR), 0.0, 1.0)
        )
        if required_experience > 0 else 0.0
    )

    # Mild penalty when semantic relevance is very weak.
    semantic_penalty = (
        _clamp(float(SEMANTIC_PENALTY_VALUE), 0.0, 1.0)
        if semantic_score < _clamp(float(SEMANTIC_PENALTY_THRESHOLD), 0.0, 1.0)
        else 0.0
    )

    raw_total = must_have_penalty + experience_gap_penalty + semantic_penalty
    total_penalty = min(_clamp(float(TOTAL_PENALTY_MAX), 0.0, 1.0), raw_total)

    return {
        "must_have_penalty": must_have_penalty,
        "experience_gap_penalty": experience_gap_penalty,
        "semantic_penalty": semantic_penalty,
        "total_penalty": total_penalty,
    }

def compute_scores(semantic_score: float, resume_skills: List[str],
                   resume_experience: float, job_data: Dict[str, Any],
                   resume_text_len: int = 0,
                   qualification_match: Optional[Dict] = None,
                   custom_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Aggregates all scores into a final weighted score.
    Considers semantic similarity, weighted skill matching, experience, and qualification.
    """
    # Use custom weights if provided, otherwise fallback to defaults
    s_weight  = custom_weights.get("semantic",       SEMANTIC_WEIGHT)       if custom_weights else SEMANTIC_WEIGHT
    sk_weight = custom_weights.get("skill",          SKILL_WEIGHT)          if custom_weights else SKILL_WEIGHT
    e_weight  = custom_weights.get("experience",     EXPERIENCE_WEIGHT)     if custom_weights else EXPERIENCE_WEIGHT
    q_weight  = custom_weights.get("qualification",  QUALIFICATION_WEIGHT)  if custom_weights else QUALIFICATION_WEIGHT

    # Guard against malformed custom weights.
    s_weight = max(0.0, float(s_weight))
    sk_weight = max(0.0, float(sk_weight))
    e_weight = max(0.0, float(e_weight))
    q_weight = max(0.0, float(q_weight))

    # Normalise weights to sum to 1.0 (safety net)
    total_w = s_weight + sk_weight + e_weight + q_weight
    if total_w > 0:
        s_weight /= total_w
        sk_weight /= total_w
        e_weight /= total_w
        q_weight /= total_w
    else:
        # Fallback to stable defaults if custom weights collapse to zero.
        s_weight = SEMANTIC_WEIGHT
        sk_weight = SKILL_WEIGHT
        e_weight = EXPERIENCE_WEIGHT
        q_weight = QUALIFICATION_WEIGHT
        total_w = s_weight + sk_weight + e_weight + q_weight
        s_weight /= total_w
        sk_weight /= total_w
        e_weight /= total_w
        q_weight /= total_w

    semantic_score = _clamp(float(semantic_score) if semantic_score is not None else 0.0)

    must_original = list(job_data.get("must_have_skills", []) or [])
    good_original = list(job_data.get("good_to_have_skills", []) or [])
    req_exp = float(job_data.get("required_experience", 0) or 0)

    must_lower = _normalize_set(must_original)
    good_lower = _normalize_set(good_original)
    # Avoid double-counting if the same skill appears in both must-have and good-to-have.
    good_lower -= must_lower
    resume_lower = _normalize_set(resume_skills)

    matched_must_lower = must_lower & resume_lower
    matched_good_lower = good_lower & resume_lower
    missing_must_lower = must_lower - matched_must_lower

    matched_skills = _find_original(matched_must_lower | matched_good_lower,
                                     must_original + good_original)
    missing_skills = _find_original(missing_must_lower, must_original)

    # Weighted Skill Scoring: Must Have = 2x, Good to Have = 1x
    total_weight = len(must_lower) * 2.0 + len(good_lower) * 1.0
    if total_weight > 0:
        skill_score = (
            len(matched_must_lower) * 2.0 + len(matched_good_lower) * 1.0
        ) / total_weight
    else:
        skill_score = 0.5

    skill_score = _clamp(skill_score)

    experience_score = compute_experience_score(resume_experience, req_exp)

    # Contextualize tenure with actual skill alignment so experience fit reflects role relevance.
    contextual_experience = experience_score * (0.35 + (0.65 * skill_score))

    # --- QUALIFICATION SCORE ---
    # 1.0 if matched or not required, 0.5 partial, 0.0 hard mismatch
    if qualification_match is None:
        qual_score = 1.0  # Not required — no penalty
    elif qualification_match.get("matched"):
        qual_score = 1.0
    else:
        # Partial credit based on detail string (e.g. year mismatch vs degree mismatch)
        detail = qualification_match.get("details", "").lower()
        qual_score = 0.4 if "year" in detail else 0.1

    # We apply a final unified "Alignment Factor" rather than an arbitrary "penalty".
    # This softly scales down candidates heavily lacking primary skills.
    missing_ratio = (len(missing_must_lower) / len(must_lower)) if must_lower else 0.0
    alignment_factor = 1.0 - (0.35 * missing_ratio)  # Max 35% reduction for missing 100% MUST HAVE skills

    base_score = (
        s_weight  * semantic_score +
        sk_weight * skill_score +
        e_weight  * contextual_experience +
        q_weight  * qual_score
    )

    # Final logic mathematically unifies without breaking standard scaling
    aligned_score = _clamp(base_score * alignment_factor)

    # Explicit penalty layer (added on top, keeps base scoring formula unchanged).
    penalty_parts = _compute_additional_penalty(
        missing_must_count=len(missing_must_lower),
        total_must_count=len(must_lower),
        candidate_experience=resume_experience,
        required_experience=req_exp,
        semantic_score=semantic_score,
    )
    additional_penalty = penalty_parts["total_penalty"]
    final_score = _clamp(aligned_score - additional_penalty)

    # For UI breakdown compatibility
    alignment_penalty = max(0.0, base_score - aligned_score)
    penalty = alignment_penalty + additional_penalty
    irrelevancy_multiplier = alignment_factor

    confidence = _compute_confidence(
        resume_text_len=resume_text_len,
        skills_found=len(resume_skills) if resume_skills else 0,
        has_experience=resume_experience is not None and float(resume_experience) > 0
    )

    return {
        "semantic_score":    round(semantic_score, 3),
        "skill_score":       round(skill_score, 3),
        "experience_score":  round(contextual_experience, 3),
        "experience_score_raw": round(experience_score, 3),
        "qualification_score": round(qual_score, 3),
        "final_score":       round(final_score, 3),
        "matched_skills":    matched_skills,
        "missing_skills":    missing_skills,
        "confidence":        round(confidence, 2),
        "score_breakdown": {
            "semantic_contribution":       round(s_weight  * semantic_score, 3),
            "skill_contribution":          round(sk_weight * skill_score, 3),
            "experience_contribution":     round(e_weight  * contextual_experience, 3),
            "qualification_contribution":  round(q_weight  * qual_score, 3),
            "penalty_applied":             round(penalty, 3),
            "alignment_penalty":           round(alignment_penalty, 3),
            "must_have_penalty":           round(penalty_parts["must_have_penalty"], 3),
            "experience_gap_penalty":      round(penalty_parts["experience_gap_penalty"], 3),
            "semantic_penalty":            round(penalty_parts["semantic_penalty"], 3),
            "additional_penalty":          round(additional_penalty, 3),
            "irrelevancy_multiplier":      round(irrelevancy_multiplier, 2)
        }
    }
