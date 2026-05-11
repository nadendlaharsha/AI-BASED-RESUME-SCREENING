"""
Skill Extractor Module

This module handles the extraction of skills from text using a combination of
direct matching, synonym resolution, fuzzy matching, and NLP-based entity extraction.
"""

import re
import os
import json
from typing import List, Dict, Optional, Any
from rapidfuzz import fuzz, process
from core.nlp_engine import NLPEngine

# Global NLP engine instance (lazy loaded)
_nlp_engine = None

def get_nlp_engine() -> NLPEngine:
    """Lazy load the NLP engine singleton."""
    global _nlp_engine
    if _nlp_engine is None:
        _nlp_engine = NLPEngine()
    return _nlp_engine

SKILLS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "skills.json")

_skills_data = None

def _load_skills_data() -> Dict[str, Any]:
    """Load skills data from the JSON file."""
    global _skills_data
    if _skills_data is None:
        try:
            with open(SKILLS_FILE, "r", encoding="utf-8") as f:
                _skills_data = json.load(f)
                
                # Auto-generate the master "skills" list from "categories"
                # so the JSON file doesn't need to duplicate hundreds of lines.
                if "categories" in _skills_data:
                    auto_skills = set(_skills_data.get("skills", []))
                    for cat_skills in _skills_data["categories"].values():
                        auto_skills.update(cat_skills)
                    _skills_data["skills"] = sorted(list(auto_skills))
                    
        except (FileNotFoundError, json.JSONDecodeError):
            _skills_data = {"skills": [], "synonyms": {}, "categories": {}}
    return _skills_data

def get_skill_synonyms() -> Dict[str, str]:
    """Retrieve skill synonyms mapping."""
    data = _load_skills_data()
    return data.get("synonyms", {})

def get_default_skills() -> List[str]:
    """Retrieve the default list of skills."""
    data = _load_skills_data()
    return data.get("skills", [])

def normalize(text: str) -> str:
    """Normalize text by converting to lowercase and removing special characters."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s./#+\-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _deduplicate_skills(skills: List[str]) -> List[str]:
    """Remove duplicate skills while preserving order (case-insensitive check)."""
    seen = set()
    result = []
    for skill in skills:
        key = skill.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(skill)
    return result

def _resolve_synonyms(text: str, synonyms: Dict[str, str]) -> str:
    """Resolve skill synonyms in the text to their canonical forms."""
    text_norm = normalize(text)

    # Sort by length descending to match longest synonyms first
    sorted_synonyms = sorted(synonyms.items(), key=lambda x: -len(x[0]))

    for alias, canonical in sorted_synonyms:
        alias_norm = normalize(alias)
        # Match whole words only
        if alias_norm and re.search(rf"\b{re.escape(alias_norm)}\b", text_norm):
            text_norm = text_norm + " " + normalize(canonical)

    return text_norm

def _build_ngrams(words: List[str], n: int) -> List[str]:
    """Build n-grams from a list of words."""
    if n <= 0 or not words:
        return []
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]

def _direct_skill_search(text: str, skill: str) -> bool:
    """
    Check if a skill exists in the text using direct matching regex.
    """
    if not text or not skill:
        return False

    text_lower = text.lower()
    skill_lower = skill.lower().strip()
    skill_norm = normalize(skill)

    # Fast path: substring check
    if skill_lower in text_lower:
        return True

    # Regex word boundary check
    if re.search(rf"\b{re.escape(skill_norm)}\b", normalize(text)):
        return True

    # Multi-word skill check: all words must be present
    skill_words = skill_norm.split()
    if len(skill_words) > 1:
        all_present = all(
            re.search(rf"\b{re.escape(word)}\b", normalize(text))
            for word in skill_words
        )
        if all_present:
            return True

    # Single word skill fuzzy check (for short abbreviations vs words)
    # Only if skill length >= 4 to avoid false positives on short acronyms like 'C', 'R'
    if len(skill_words) == 1 and len(skill_norm) >= 4:
        text_words = normalize(text).split()
        for word in text_words:
            if len(word) >= 3 and fuzz.ratio(skill_norm, word) >= 85:
                return True

    return False

def extract_skills(text: str, skill_list: Optional[List[str]] = None,
                  threshold: int = 80) -> List[str]:
    """
    Extract skills from the provided text.

    Args:
        text: The input text (resume content).
        skill_list: Optional list of skills to search for. Defaults to known skills.
        threshold: Fuzzy matching threshold.

    Returns:
        List of extracted unique skills.
    """
    if not text:
        return []

    if skill_list is None:
        skill_list = get_default_skills()

    if not skill_list:
        return []

    aliases = get_skill_synonyms()

    text_norm = _resolve_synonyms(text, aliases)
    text_words = text_norm.split()
    found = set()

    skill_lookup = {}
    for skill in skill_list:
        norm = normalize(skill)
        if norm:
            skill_lookup[norm] = skill

    # Pre-calculate n-grams logic
    max_skill_words = max(
        (len(normalize(s).split()) for s in skill_list if s),
        default=1
    )
    max_n = min(max_skill_words, 5)

    # 1. Direct & Regex Matching
    for skill_norm, skill_original in skill_lookup.items():
        if _direct_skill_search(text, skill_original):
            found.add(skill_original)
            continue

        if re.search(rf"\b{re.escape(skill_norm)}\b", text_norm):
            found.add(skill_original)
            continue

        # (Synonyms are already pre-resolved into text_norm globally by _resolve_synonyms, 
        # so we don't need a massive O(N) secondary loop checking regexes here!)

        # Fuzzy Matching (Expensive)
        skill_word_count = len(skill_norm.split())
        candidates = _build_ngrams(text_words, skill_word_count) \
            if skill_word_count <= max_n else []

        if candidates:
            best = process.extractOne(
                skill_norm, candidates,
                scorer=fuzz.ratio,
                score_cutoff=threshold
            )
            if best:
                found.add(skill_original)

    result = []
    for sk in found:
        if sk:
            result.append(sk.title().strip())

    # --- NLP INTEGRATION ---
    try:
        nlp = get_nlp_engine()
        # Extract entities using spaCy
        potential_candidates = nlp.extract_entities(text)

        # We need a reference list of ALL known skills for validation
        all_known_skills = get_default_skills()

        # Validate found entities
        validated_nlp_skills = nlp.validate_skills(potential_candidates, all_known_skills)

        for v_skill in validated_nlp_skills:
            result.append(v_skill.title().strip())

    except Exception as e:
        # Fail silently or log, but don't break the main extraction
        print(f"NLP Extraction Warning: {e}")

    return _deduplicate_skills(result)
