"""
NLP Engine Module

This module handles Natural Language Processing tasks for the resume screening application.
It uses spaCy for Entity Recognition and RapidFuzz for fuzzy string matching to
identify skills, entities, and candidate names.
"""

import re
from typing import List, Set
import spacy
from spacy.language import Language
import functools
from rapidfuzz import process, fuzz
from core.embedding_engine import EmbeddingEngine

# Load NLP model once — prefer large model for better NER on technical entities
@functools.lru_cache(maxsize=1)
def load_nlp() -> Language:
    """Load the best available spaCy NLP model (lg > md > sm), downloading if necessary."""
    for model_name in ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"]:
        try:
            return spacy.load(model_name)
        except OSError:
            try:
                from spacy.cli import download
                download(model_name)
                return spacy.load(model_name)
            except Exception:
                continue
    raise RuntimeError("No spaCy English model could be loaded. Run: python -m spacy download en_core_web_lg")


class NLPEngine:
    """
    Engine for performing NLP tasks extraction and validation.
    """

    STOP_WORDS = {
        "experience", "skills", "education", "project", "work", "role", "team", "company"
    }

    def __init__(self):
        """Initialize the NLP engine with spaCy model and embedding engine."""
        self.nlp = load_nlp()
        self.embedder = EmbeddingEngine()

    def extract_entities(self, text: str) -> Set[str]:
        """
        Extract potential skills using NER and pattern matching.
        Focuses on ORG (Organizations/Companies/Frameworks), PRODUCT, and WORK_OF_ART.
        """
        doc = self.nlp(text)
        candidates = set()

        # 1. Named Entity Recognition
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PRODUCT", "WORK_OF_ART", "GPE", "LANGUAGE"]:
                clean_ent = self._clean_term(ent.text)
                if self._is_valid_candidate(clean_ent):
                    candidates.add(clean_ent)

        # 2. Pattern Matching (Noun Phrases that look technical)
        # Look for terms like "AWS Lambda", "Google Cloud", "React Native"
        for chunk in doc.noun_chunks:
            clean_chunk = self._clean_term(chunk.text)
            if 2 <= len(clean_chunk.split()) <= 3 and self._is_valid_candidate(clean_chunk):
                candidates.add(clean_chunk)

        return candidates

    def _clean_term(self, term: str) -> str:
        """Clean a term by removing special characters."""
        return re.sub(r'[^a-zA-Z0-9\s\+\#\.]', '', term).strip()

    def _is_valid_candidate(self, term: str) -> bool:
        """Check if a term is a valid skill candidate."""
        if not term or len(term) < 2:
            return False
        if term.lower() in self.STOP_WORDS:
            return False
        if term.isdigit():  # skip years like '2020'
            return False
        return True

    def validate_skills(self, candidates: Set[str], known_skills: List[str]) -> List[str]:
        """
        Validate extracted candidates against a known skill database using fuzzy matching.
        This bridges the gap between 'extracted text' and 'actual skill'.
        """
        validated = set()

        # Optimize by set lookups first (case-insensitive)
        known_map = {k.lower(): k for k in known_skills}

        for cand in candidates:
            cand_lower = cand.lower()

            # Direct match
            if cand_lower in known_map:
                validated.add(known_map[cand_lower])
                continue

            # Fuzzy match (expensive, use sparingly or with limited threshold)
            # Only fuzzy match if it looks promising
            match = process.extractOne(cand_lower, list(known_map.keys()), scorer=fuzz.ratio)
            if match and match[1] >= 90:  # Very High confidence only to avoid false positives
                validated.add(known_map[match[0]])

        return list(validated)
