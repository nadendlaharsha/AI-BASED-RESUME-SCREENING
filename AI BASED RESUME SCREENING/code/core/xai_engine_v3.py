"""
XAI Engine v3 — Structured, Dynamic, Per-Candidate Recruiter Analysis.

Returns a rich JSON object (not flat text) so the frontend can render
each candidate's analysis with unique visual components.
"""

import re


_STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "have", "will", "your",
    "you", "our", "are", "role", "job", "must", "should", "years", "year", "experience",
    "candidate", "skills", "ability", "work", "team", "using", "strong", "good", "knowledge",
    "developer", "development", "requirements", "responsibilities"
}


def _top_job_keywords(job_description: str, limit: int = 10):
    if not job_description:
        return []
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", job_description.lower())
    seen = set()
    keywords = []
    for w in words:
        if w in _STOP_WORDS or w in seen:
            continue
        seen.add(w)
        keywords.append(w)
        if len(keywords) >= limit:
            break
    return keywords


def _resume_keyword_hits(resume_text: str, keywords):
    if not resume_text or not keywords:
        return []
    text = resume_text.lower()
    return [k for k in keywords if re.search(rf"\b{re.escape(k)}\b", text)]


def _evidence_snippets(resume_text: str, terms, max_items: int = 3):
    if not resume_text or not terms:
        return []

    text = re.sub(r"\s+", " ", resume_text).strip()
    snippets = []
    seen = set()
    for term in terms:
        m = re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE)
        if not m:
            continue
        start = max(0, m.start() - 50)
        end = min(len(text), m.end() + 55)
        snippet = text[start:end].strip()
        snippet = ("..." + snippet) if start > 0 else snippet
        snippet = (snippet + "...") if end < len(text) else snippet
        if snippet and snippet not in seen:
            snippets.append({"term": term, "text": snippet})
            seen.add(snippet)
        if len(snippets) >= max_items:
            break
    return snippets


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    if isinstance(value, str):
        return [value] if value.strip() else []
    return []


def _normalize_qualifications(quals):
    """Convert qualification payloads (str/list/dict) into a display-safe list."""
    if not quals:
        return []

    if isinstance(quals, str):
        return [quals]

    if isinstance(quals, list):
        return [str(q) for q in quals if q]

    if isinstance(quals, dict):
        out = []
        highest = quals.get("highest_degree")
        qual_text = quals.get("qualification_text")
        years = quals.get("year_of_passing")
        degrees = _as_list(quals.get("degrees"))

        if highest:
            out.append(str(highest))
        if qual_text and str(qual_text) not in out:
            out.append(str(qual_text))
        if years:
            out.append(f"Year: {years}")
        for d in degrees[:2]:
            ds = str(d)
            if ds not in out:
                out.append(ds)
        return out

    return [str(quals)]


def _band(value: float) -> str:
    if value >= 0.85:
        return "strong"
    if value >= 0.65:
        return "good"
    if value >= 0.45:
        return "moderate"
    return "weak"


def _verdict(final_score: float) -> dict:
    if final_score >= 0.85:
        return {"label": "Strong Fit", "color": "green", "icon": "🟢"}
    if final_score >= 0.65:
        return {"label": "Good Fit", "color": "blue", "icon": "🔵"}
    if final_score >= 0.45:
        return {"label": "Moderate Fit", "color": "amber", "icon": "🟡"}
    return {"label": "Weak Fit", "color": "red", "icon": "🔴"}


def _generate_strengths(scores, matched, candidate, job_data, jd_hits):
    """Dynamically generate strengths based on actual candidate data."""
    strengths = []
    semantic = float(scores.get("semantic_score", 0) or 0)
    skill_score = float(scores.get("skill_score", 0) or 0)
    exp_score = float(scores.get("experience_score", 0) or 0)
    cand_exp = float(candidate.get("experience", 0) or 0)
    req_exp = float(job_data.get("required_experience", 0) or 0)
    must_have = set(s.lower() for s in (job_data.get("must_have_skills", []) or []))
    matched_must = [s for s in matched if s.lower() in must_have]

    # Semantic relevance
    if semantic >= 0.7:
        strengths.append({
            "title": "High Domain Relevance",
            "detail": f"Resume content is {semantic:.0%} semantically aligned with the job description, indicating strong domain expertise."
        })
    elif semantic >= 0.5:
        strengths.append({
            "title": "Good Domain Match",
            "detail": f"Resume shows {semantic:.0%} semantic alignment with the role requirements."
        })

    # Skill coverage
    if skill_score >= 0.9:
        strengths.append({
            "title": "Exceptional Skill Coverage",
            "detail": f"Covers {skill_score:.0%} of required skills — nearly complete match across all requirements."
        })
    elif skill_score >= 0.7:
        strengths.append({
            "title": "Strong Skill Match",
            "detail": f"Matches {skill_score:.0%} of required skills with {len(matched)} skills identified."
        })

    # Must-have skills
    if must_have and len(matched_must) == len(must_have):
        strengths.append({
            "title": "All Must-Have Skills Present",
            "detail": f"Covers all {len(must_have)} critical must-have skills: {', '.join(matched_must[:5])}."
        })
    elif must_have and len(matched_must) >= len(must_have) * 0.7:
        strengths.append({
            "title": "Most Must-Have Skills Covered",
            "detail": f"Matches {len(matched_must)} of {len(must_have)} must-have skills."
        })

    # Experience
    if req_exp > 0 and cand_exp >= req_exp:
        extra = cand_exp - req_exp
        if extra >= 2:
            strengths.append({
                "title": "Exceeds Experience Requirement",
                "detail": f"Has {cand_exp:.1f} years of experience — {extra:.1f} years above the {req_exp:.1f}-year requirement."
            })
        else:
            strengths.append({
                "title": "Meets Experience Requirement",
                "detail": f"Has {cand_exp:.1f} years of experience, meeting the {req_exp:.1f}-year requirement."
            })
    elif req_exp <= 0 and cand_exp >= 3:
        strengths.append({
            "title": "Solid Experience Base",
            "detail": f"Brings {cand_exp:.1f} years of professional experience to the role."
        })

    # JD keyword evidence
    if len(jd_hits) >= 5:
        strengths.append({
            "title": "Rich Keyword Alignment",
            "detail": f"Resume directly references {len(jd_hits)} key terms from the job description."
        })

    # Projects
    projects = candidate.get("projects", [])
    if projects and len(projects) >= 2:
        strengths.append({
            "title": "Project Experience",
            "detail": f"Demonstrates {len(projects)} relevant projects showing applied skills."
        })

    # Contact completeness
    contact_fields = sum(1 for f in ["email", "phone", "linkedin", "github"] if candidate.get(f))
    if contact_fields >= 3:
        strengths.append({
            "title": "Complete Contact Profile",
            "detail": f"Provides {contact_fields} contact channels including professional profiles."
        })

    return strengths


def _generate_risks(scores, missing, candidate, job_data):
    """Dynamically generate risks and gaps based on actual candidate data."""
    risks = []
    semantic = float(scores.get("semantic_score", 0) or 0)
    skill_score = float(scores.get("skill_score", 0) or 0)
    cand_exp = float(candidate.get("experience", 0) or 0)
    req_exp = float(job_data.get("required_experience", 0) or 0)
    must_have = set(s.lower() for s in (job_data.get("must_have_skills", []) or []))
    missing_must = [s for s in missing if s.lower() in must_have]
    confidence = float(scores.get("confidence", 1.0) or 1.0)
    breakdown = scores.get("score_breakdown", {}) or {}

    # Missing must-have skills
    if missing_must:
        severity = "high" if len(missing_must) >= 2 else "medium"
        risks.append({
            "title": f"Missing {len(missing_must)} Must-Have Skill{'s' if len(missing_must) > 1 else ''}",
            "detail": f"Critical gaps: {', '.join(missing_must[:4])}. These are marked as essential for the role.",
            "severity": severity
        })

    # Missing good-to-have skills
    missing_good = [s for s in missing if s.lower() not in must_have]
    if missing_good and len(missing_good) >= 2:
        risks.append({
            "title": f"Missing {len(missing_good)} Good-to-Have Skills",
            "detail": f"Not found: {', '.join(missing_good[:4])}. May require additional training.",
            "severity": "low"
        })

    # Experience gap
    if req_exp > 0 and cand_exp < req_exp:
        gap = req_exp - cand_exp
        severity = "high" if gap >= 2 else "medium"
        risks.append({
            "title": "Experience Gap",
            "detail": f"Has {cand_exp:.1f} years vs required {req_exp:.1f} years — a gap of {gap:.1f} year{'s' if gap != 1 else ''}.",
            "severity": severity
        })

    # Low semantic relevance
    if semantic < 0.35:
        risks.append({
            "title": "Low Domain Relevance",
            "detail": f"Only {semantic:.0%} semantic match — resume content may not align well with the job domain.",
            "severity": "high"
        })
    elif semantic < 0.5:
        risks.append({
            "title": "Moderate Domain Fit",
            "detail": f"Semantic alignment is {semantic:.0%} — some domain relevance but not a strong match.",
            "severity": "medium"
        })

    # Low confidence in parsing
    if confidence < 0.6:
        risks.append({
            "title": "Low Parsing Confidence",
            "detail": f"Resume parsing confidence is {confidence:.0%}. Some data may be incomplete or inaccurate.",
            "severity": "medium"
        })

    # Penalty-heavy score
    penalty = float(breakdown.get("penalty_applied", 0) or 0)
    if penalty >= 0.1:
        risks.append({
            "title": "Significant Score Penalties",
            "detail": f"A {penalty:.0%} penalty was applied due to skill/experience gaps, reducing the final score.",
            "severity": "medium"
        })

    return risks


def _generate_verdict_reason(verdict_info, scores, matched, missing, candidate, job_data):
    """Generate a unique, natural-language verdict sentence for this candidate."""
    final = float(scores.get("final_score", 0) or 0)
    semantic = float(scores.get("semantic_score", 0) or 0)
    skill_score = float(scores.get("skill_score", 0) or 0)
    cand_exp = float(candidate.get("experience", 0) or 0)
    req_exp = float(job_data.get("required_experience", 0) or 0)
    name = candidate.get("resume_name") or candidate.get("resume_filename") or "This candidate"
    breakdown = scores.get("score_breakdown", {}) or {}

    # Find the top contributing factor
    factors = [
        ("domain expertise", float(breakdown.get("semantic_contribution", 0) or 0)),
        ("skill alignment", float(breakdown.get("skill_contribution", 0) or 0)),
        ("experience fit", float(breakdown.get("experience_contribution", 0) or 0)),
    ]
    top_factor = max(factors, key=lambda x: x[1])[0]

    if final >= 0.85:
        if not missing:
            return f"{name} is an outstanding match — covers all required skills with {semantic:.0%} domain relevance and {cand_exp:.1f} years of experience."
        return f"{name} scores exceptionally well, driven primarily by {top_factor}, making them a top-tier candidate for this role."
    elif final >= 0.65:
        if missing:
            return f"{name} is a solid candidate with strengths in {top_factor}, though {len(missing)} skill gap{'s' if len(missing) > 1 else ''} should be noted."
        return f"{name} demonstrates strong alignment through {top_factor} and covers all required skills."
    elif final >= 0.45:
        if req_exp > 0 and cand_exp < req_exp:
            return f"{name} shows potential but has an experience gap ({cand_exp:.1f}/{req_exp:.1f} years) and {len(missing)} missing skill{'s' if len(missing) > 1 else ''} to address."
        return f"{name} has moderate alignment — {top_factor} is the strongest area, but overall fit needs improvement."
    else:
        return f"{name} has limited alignment with this role — significant gaps in {top_factor} and skill coverage suggest a poor match."


def _generate_recommendation(verdict_info, strengths, risks):
    """Generate a final actionable recommendation for the recruiter."""
    label = verdict_info["label"]
    high_risks = [r for r in risks if r.get("severity") == "high"]

    if label == "Strong Fit":
        return "Recommend advancing to interview — strong alignment across all evaluation dimensions."
    elif label == "Good Fit":
        if high_risks:
            risk_areas = ", ".join(r["title"].lower() for r in high_risks[:2])
            return f"Worth considering for interview — discuss {risk_areas} during screening."
        return "Solid candidate — recommend scheduling an initial interview to verify fit."
    elif label == "Moderate Fit":
        if strengths:
            top_strength = strengths[0]["title"].lower()
            return f"Consider if {top_strength} outweighs the identified gaps. May need further evaluation."
        return "Borderline candidate — compare against stronger applicants before deciding."
    else:
        if strengths:
            return "Not recommended for this role. Consider for junior positions or different roles that match their strengths."
        return "Not recommended — significant misalignment with role requirements."


def _confidence_level(final_score: float, risks) -> str:
    high_risk_count = len([r for r in (risks or []) if r.get("severity") == "high"])
    if final_score >= 0.8 and high_risk_count == 0:
        return "High"
    if final_score >= 0.6 and high_risk_count <= 1:
        return "Medium"
    return "Low"


def _interview_focus_points(skill_analysis, experience_analysis, risks, max_items: int = 2):
    points = []
    missing_must = (skill_analysis or {}).get("missing_must", []) or []
    if missing_must:
        skill = missing_must[0]
        points.append(f"Validate practical depth in {skill} with a short hands-on scenario.")

    exp = experience_analysis or {}
    req = float(exp.get("required_years", 0) or 0)
    cand = float(exp.get("candidate_years", 0) or 0)
    if req > 0 and cand < req:
        points.append("Probe ownership level in past projects to confirm readiness for this role's scope.")

    high_risks = [r for r in (risks or []) if r.get("severity") == "high"]
    if high_risks:
        points.append(f"Clarify risk area: {high_risks[0].get('title', 'critical requirement gap')}.")

    if not points:
        points.append("Use role-specific system-design and problem-solving questions to validate consistency.")

    return points[:max_items]


def _build_executive_brief(candidate_name, verdict_info, final_score, strengths, risks, skill_analysis, experience_analysis, recommendation):
    strengths = strengths or []
    risks = risks or []
    top_strength = strengths[0]["title"] if strengths else "overall profile alignment"
    top_risk = risks[0]["title"] if risks else "no major risk flags"

    decision_line = (
        f"{candidate_name}: {verdict_info['label']} ({final_score:.1%}) based on {top_strength.lower()}."
    )

    return {
        "decision": verdict_info.get("label", "Review Needed"),
        "confidence": _confidence_level(final_score, risks),
        "decision_line": decision_line,
        "primary_reason": top_strength,
        "primary_concern": top_risk,
        "next_step": recommendation,
        "interview_focus": _interview_focus_points(skill_analysis, experience_analysis, risks),
    }


def generate_text_based_xai(job_data: dict, candidate: dict) -> dict:
    """
    Generates a structured, dynamic, per-candidate analysis.
    Returns a rich dict (not flat text) for the frontend to render visually.
    """
    candidate = candidate or {}
    job_data = job_data or {}
    scores = candidate.get("scores", {}) or {}
    final_score = float(scores.get("final_score", 0) or 0)
    matched = _as_list(scores.get("matched_skills", []))
    missing = _as_list(scores.get("missing_skills", []))
    breakdown = scores.get("score_breakdown", {}) or {}

    must_have = set(str(s).lower() for s in _as_list(job_data.get("must_have_skills", [])))
    good_have = set(str(s).lower() for s in _as_list(job_data.get("good_to_have_skills", [])))
    all_required = must_have | good_have
    total_required = len(all_required) if all_required else 1

    candidate_name = candidate.get("resume_name") or candidate.get("resume_filename") or "Candidate"

    semantic = float(scores.get("semantic_score", 0) or 0)
    skill_score = float(scores.get("skill_score", 0) or 0)
    exp_score = float(scores.get("experience_score", 0) or 0)
    exp_raw = float(scores.get("experience_score_raw", exp_score) or 0)
    qual_score = float(scores.get("qualification_score", 1.0) or 1.0)
    req_exp = float(job_data.get("required_experience", 0) or 0)
    cand_exp = float(candidate.get("experience", 0) or 0)

    jd_keywords = _top_job_keywords(job_data.get("job_description", ""))
    jd_hits = _resume_keyword_hits(candidate.get("resume_text", ""), jd_keywords)

    # --- Verdict ---
    verdict_info = _verdict(final_score)

    # --- Score Factors ---
    score_factors = [
        {
            "name": "Domain Relevance",
            "value": round(semantic, 3),
            "contribution": round(float(breakdown.get("semantic_contribution", 0) or 0), 3),
            "label": _band(semantic),
            "icon": "🎯"
        },
        {
            "name": "Skill Match",
            "value": round(skill_score, 3),
            "contribution": round(float(breakdown.get("skill_contribution", 0) or 0), 3),
            "label": _band(skill_score),
            "icon": "🛠️"
        },
        {
            "name": "Experience Fit",
            "value": round(exp_score, 3),
            "contribution": round(float(breakdown.get("experience_contribution", 0) or 0), 3),
            "label": _band(exp_score),
            "icon": "📅"
        },
        {
            "name": "Qualification",
            "value": round(qual_score, 3),
            "contribution": round(float(breakdown.get("qualification_contribution", 0) or 0), 3),
            "label": _band(qual_score),
            "icon": "🎓"
        },
    ]

    # --- Dynamic Strengths & Risks ---
    strengths = _generate_strengths(scores, matched, candidate, job_data, jd_hits)
    risks = _generate_risks(scores, missing, candidate, job_data)

    # --- Verdict Reason (unique sentence per candidate) ---
    verdict_reason = _generate_verdict_reason(verdict_info, scores, matched, missing, candidate, job_data)

    # --- Skill Analysis ---
    matched_must = [s for s in matched if s.lower() in must_have]
    matched_good = [s for s in matched if s.lower() in good_have]
    missing_must = [s for s in missing if s.lower() in must_have]
    missing_good = [s for s in missing if s.lower() not in must_have]
    coverage_pct = round((len(matched) / total_required) * 100) if total_required > 0 else 0

    skill_analysis = {
        "matched": matched,
        "matched_must": matched_must,
        "matched_good": matched_good,
        "missing": missing,
        "missing_must": missing_must,
        "missing_good": missing_good,
        "coverage_pct": coverage_pct,
        "total_required": len(all_required),
    }

    # --- Experience Analysis ---
    if req_exp > 0:
        if cand_exp >= req_exp:
            exp_verdict = "Meets requirement"
        elif cand_exp >= req_exp * 0.7:
            exp_verdict = "Slightly below"
        else:
            exp_verdict = "Below requirement"
    else:
        exp_verdict = "Not required"

    experience_analysis = {
        "candidate_years": round(cand_exp, 1),
        "required_years": round(req_exp, 1),
        "raw_score": round(exp_raw, 3),
        "contextual_score": round(exp_score, 3),
        "verdict": exp_verdict,
    }

    # --- Evidence Snippets ---
    evidence = _evidence_snippets(candidate.get("resume_text", ""), jd_hits, max_items=3)

    # --- Penalty Breakdown ---
    penalty_info = {
        "total": round(float(breakdown.get("penalty_applied", 0) or 0), 3),
        "must_have": round(float(breakdown.get("must_have_penalty", 0) or 0), 3),
        "experience_gap": round(float(breakdown.get("experience_gap_penalty", 0) or 0), 3),
        "semantic": round(float(breakdown.get("semantic_penalty", 0) or 0), 3),
        "alignment_factor": round(float(breakdown.get("irrelevancy_multiplier", 1.0) or 1.0), 2),
    }

    # --- Recommendation ---
    recommendation = _generate_recommendation(verdict_info, strengths, risks)

    # --- Qualifications ---
    quals = _normalize_qualifications(candidate.get("qualifications"))

    # --- Text Summary (for backward compat / CSV export) ---
    text_summary = (
        f"Candidate: {candidate_name}. "
        f"Verdict: {verdict_info['label']} ({final_score:.1%}). "
        f"{verdict_reason} "
        f"Matched skills: {', '.join(matched) if matched else 'None'}. "
        f"Missing skills: {', '.join(missing) if missing else 'None'}. "
        f"Experience: {cand_exp:.1f} years (required: {req_exp:.1f}). "
        f"{recommendation}"
    )

    executive_brief = _build_executive_brief(
        candidate_name,
        verdict_info,
        final_score,
        strengths,
        risks,
        skill_analysis,
        experience_analysis,
        recommendation,
    )

    return {
        "candidate_name": candidate_name,
        "final_score": round(final_score, 3),
        "verdict": verdict_info,
        "verdict_reason": verdict_reason,
        "score_factors": score_factors,
        "strengths": strengths,
        "risks": risks,
        "skill_analysis": skill_analysis,
        "experience_analysis": experience_analysis,
        "evidence_snippets": evidence,
        "penalty_info": penalty_info,
        "qualifications": quals[:3],
        "recommendation": recommendation,
        "executive_brief": executive_brief,
        "text_summary": text_summary,
    }
