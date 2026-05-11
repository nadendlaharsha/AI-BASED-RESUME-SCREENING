"""
Qualification Extractor Module

Extracts educational qualifications and degrees from resume text.
"""

import re
from typing import List, Dict, Optional, Any
from datetime import datetime


def _simplify_degree_token(text: str) -> str:
    """Uppercase and remove non-alphanumeric characters.

    Examples:
    - "M.Tech" -> "MTECH"
    - "Bachelor's" -> "BACHELORS"
    """
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def _degree_level_from_text(degree_text: str) -> Optional[str]:
    """Infer degree level from a degree string.

    For short tokens such as MS, ME, BA, BS we require that they appear as the
    *entire* normalized string or at a clear boundary — otherwise words like
    INTERMEDIATE, SYSTEMS, etc. produce false positives.

    Short patterns (<=4 chars) are checked via **word-boundary search** in the
    original text rather than substring search in the stripped/concatenated
    form.  This prevents false positives like "FEEDBACK" → "DBA" or
    "COMBAT" → "MBA" while correctly matching "MBA in Finance".
    """
    t = _simplify_degree_token(degree_text)
    if not t:
        return None

    # Upper-cased original text for word-boundary checks on short patterns.
    upper_orig = (degree_text or "").upper().strip()

    def _has_short(pattern: str) -> bool:
        """Return True if a short pattern (<=4 chars) legitimately appears.

        We require either:
          - exact match on the simplified text  (e.g., input is just "MBA"), OR
          - the pattern exists as a standalone word in the original text.

        This avoids false positives from concatenated text where "DBA"
        hides inside "FEEDBACK" or "MBA" inside "COMBAT".
        """
        if t == pattern:
            return True
        if re.search(r"\b" + re.escape(pattern) + r"\b", upper_orig):
            return True
        return False

    # ── Doctorate ─────────────────────────────────────────────────
    if any(_has_short(k) for k in ["PHD", "DBA", "EDD"]):
        return "doctorate"
    if any(re.search(r"\b" + k + r"\b", upper_orig) for k in ["DOCTORATE", "DOCTOR OF PHILOSOPHY", "JURIS DOCTOR", "DOCTOR OF MEDICINE"]):
        return "doctorate"
    if t in ("MD", "JD"):
        return "doctorate"

    # ── Masters ───────────────────────────────────────────────────
    # We must use word boundary checks for "MASTER" to avoid matching "MASTERED", "WEBMASTER" etc.
    if any(re.search(r"\b" + k + r"\b", upper_orig) for k in ["MASTER", "MASTERS", "MASTER'S", "POSTGRADUATE"]):
        return "masters"
    if any(k in t for k in ["MTECH", "MPHIL"]):
        if not re.search(r"\b(MASTERED|WEBMASTER|SCRUMMASTER)\b", upper_orig):
            return "masters"
    # Short tokens — word-boundary check to avoid false positives
    if any(_has_short(k) for k in ["MBA", "MCA", "LLM", "MSC", "MENG", "MCOM", "PG"]):
        return "masters"
    # Very short exact match
    for k in ["MS", "ME", "MA", "MED"]:
        if t == k:
            return "masters"

    # ── Bachelors ─────────────────────────────────────────────────
    if any(re.search(r"\b" + k + r"\b", upper_orig) for k in ["BACHELOR", "BACHELORS", "BACHELOR'S", "UNDERGRADUATE"]):
        return "bachelors"
    if any(k in t for k in ["BTECH", "BARCH", "BPHARM"]):
        return "bachelors"
    if any(_has_short(k) for k in ["BBA", "BCA", "LLB", "BSC", "BENG", "BCOM", "UG"]):
        return "bachelors"
    for k in ["BS", "BE", "BA", "BED"]:
        if t == k:
            return "bachelors"

    # ── Associate ─────────────────────────────────────────────────
    # "ASSOCIATE" (9 chars) is safe as substring only if it's a complete
    # word — "ASSOCIATED" should NOT match.
    if re.search(r"\bASSOCIATE\b", upper_orig):
        return "associate"
    if any(_has_short(k) for k in ["AAS"]):
        return "associate"
    if t in ("AS", "AA"):
        return "associate"

    # ── Diploma ───────────────────────────────────────────────────
    if any(k in t for k in ["DIPLOMA", "POSTGRADUATEDIPLOMA"]):
        return "diploma"
    if any(_has_short(k) for k in ["PGDM", "PGDCA"]):
        return "diploma"

    # ── Certificate ───────────────────────────────────────────────
    if any(k in t for k in ["CERTIFICATE", "CERTIFICATION"]):
        return "certificate"

    return None


def _extract_education_block(text: str) -> str:
    """Try to extract a likely Education section block from resume text."""
    if not text:
        return ""

    lines = [ln.strip() for ln in text.splitlines()]
    if not lines:
        return ""

    # Broader set of education-section headers
    edu_header = re.compile(
        r"\b(EDUCATION|EDUCATIONAL\s+BACKGROUND|ACADEMIC|ACADEMIC\s+BACKGROUND|QUALIFICATION(?:S)?|ACADEMIC\s+DETAILS?)\b",
        re.IGNORECASE,
    )

    start_idx = None
    for i, ln in enumerate(lines):
        if edu_header.search(ln):
            start_idx = i
            break

    if start_idx is None:
        return ""

    # Stop at next common section header (but NOT "INTERMEDIATE" which is a degree)
    stop_header = re.compile(
        r"^\s*(?:EXPERIENCE|WORK\s+EXPERIENCE|INDUSTRY\s+EXPERIENCE|TECHNICAL\s+SKILLS|SKILLS|PROJECTS|CERTIFICATIONS?|ACHIEVEMENTS|SUMMARY|PROFILE|INTERNSHIPS?|PUBLICATIONS?|OBJECTIVE|HOBBIES|EXTRACURRICULAR|HONORS|AWARDS|REFERENCES|CONTACT)\s*:?\s*$",
        re.IGNORECASE,
    )

    block_lines: List[str] = []
    for ln in lines[start_idx + 1 :]:
        if stop_header.search(ln):
            break
        # Avoid collecting a huge block in noisy resumes
        block_lines.append(ln)
        if len(block_lines) >= 40:
            break

    return "\n".join([ln for ln in block_lines if ln])


def _extract_graduation_year(text: str) -> Optional[int]:
    """Extract the most likely graduation / completion year.

    Strategy (in priority order):
      1. Explicit indicators anywhere (e.g. "Class of 2026", "Expected 2026").
      2. Explicit year ranges in the education block (e.g. "2022 - 2026").
      3. "Present / Current" ranges in the education block → estimate end year.
      4. Context window around degree keywords (captures dates on next lines).
      5. Fallback to the most recent plausible year in the full text.
    """
    if not text:
        return None

    year_re = re.compile(r"\b(20[0-2][0-9]|19[7-9][0-9])\b")
    range_re = re.compile(
        r"\b(19[7-9][0-9]|20[0-2][0-9])\s*(?:-|–|—|to)\s*(19[7-9][0-9]|20[0-2][0-9]|[0-9]{2})\b",
        re.IGNORECASE,
    )
    present_range_re = re.compile(
        r"\b(19[7-9][0-9]|20[0-2][0-9])\s*(?:-|–|—|to)\s*(present|current|now|pursuing|ongoing)\b",
        re.IGNORECASE,
    )
    explicit_grad_re = re.compile(
        r"(?:class\s+of|graduat(?:ed|ing|ion)|anticipated|expected|pass(?:out)?\s*year|completing|completed)(?:\s+in|:|-)?\s*(?:[a-zA-Z]+\s+)?(20[0-2][0-9]|19[7-9][0-9])\b",
        re.IGNORECASE,
    )

    education_block = _extract_education_block(text)

    def end_years_from_ranges(blob: str) -> List[int]:
        """Return end-years from explicit year–year ranges."""
        years: List[int] = []
        for _start, end in range_re.findall(blob):
            try:
                end_yr = int(end)
                if end_yr < 100:
                    end_yr += 2000 if end_yr < 50 else 1900
                years.append(end_yr)
            except Exception:
                pass
        return years

    def standalone_years(blob: str) -> List[int]:
        """Return all standalone year mentions, EXCLUDING those part of a range."""
        masked_blob = range_re.sub(" [RANGE] ", blob)
        masked_blob = present_range_re.sub(" [PRESENT_RANGE] ", masked_blob)
        years: List[int] = []
        for y in year_re.findall(masked_blob):
            try:
                years.append(int(y))
            except Exception:
                pass
        return years

    def estimate_present_range(blob: str) -> Optional[int]:
        """Estimate graduation year from ranges like '2022 - Present'."""
        present_ranges = present_range_re.findall(blob)
        if not present_ranges:
            return None
        starts = []
        for start, _tag in present_ranges:
            try:
                starts.append(int(start))
            except Exception:
                pass
        if not starts:
            return None
        start_year = max(starts)
        level_hint = _degree_level_from_text(blob) or _degree_level_from_text(text)
        duration = 4 if level_hint == "bachelors" else 2 if level_hint == "masters" else 4
        est = start_year + duration
        current_year = datetime.now().year
        if est < start_year:
            return None
        if est > current_year + 6:
            est = current_year + 1
        return est

    # 1) Look for explicit graduation indicator ANYWHERE
    explicit_matches = explicit_grad_re.findall(text)
    if explicit_matches:
        try:
            return max(int(m) for m in explicit_matches)
        except Exception:
            pass

    # 2) Education block based
    if education_block:
        present_est = estimate_present_range(education_block)
        range_years = end_years_from_ranges(education_block)

        if range_years:
            best = max(range_years)
            if present_est and present_est > best:
                return present_est
            return best

        if present_est:
            return present_est

        edu_standalone = standalone_years(education_block)
        if edu_standalone:
            return max(edu_standalone)

    # 3) Lines with degree keywords + context window (handles multi-line formatting)
    candidate_years: List[int] = []
    degree_line_re = re.compile(
        r"\b(B\s*\.?\s*TECH|M\s*\.?\s*TECH|BTECH|MTECH|BACHELOR|MASTER|UNIVERSITY|COLLEGE|INSTITUTE|DEGREE)\b",
        re.IGNORECASE,
    )
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if degree_line_re.search(ln):
            start_i = max(0, i - 1)
            end_i = min(len(lines), i + 3)
            context_blob = "\n".join(lines[start_i:end_i])
            
            line_est = estimate_present_range(context_blob)
            if line_est:
                candidate_years.append(line_est)
            candidate_years.extend(end_years_from_ranges(context_blob))
            candidate_years.extend(standalone_years(context_blob))
            
    if candidate_years:
        return max(candidate_years)

    # 4) Present range anywhere in the full text
    full_est = estimate_present_range(text)
    if full_est:
        return full_est

    # 5) Fallback: most recent plausible year anywhere in the full text
    all_years = end_years_from_ranges(text) + standalone_years(text)
    return max(all_years) if all_years else None

# Common degree patterns
DEGREE_PATTERNS = [
    # Doctoral degrees
    r'\b(Ph\.?D\.?|JD|MD|Doctorate|Doctor of Philosophy|Doctor of Education|Juris Doctor|Doctor of Medicine|DBA)\b',
    
    # Master's degrees & Postgraduate
    r"\b(M\s*\.?\s*Tech|MTECH|Master'?s?\s+of\s+Technology|Masters?\s+of\s+Technology|M\s*\.?\s*Technology)\b",
    r"\b(M\.?S|MS|Master'?s?\s+of\s+Science|Masters?\s+of\s+Science|M\.?Sc|MSC)\b",
    r"\b(M\.?E|ME|M\.?Eng|MENG|Master'?s?\s+of\s+Engineering|Masters?\s+of\s+Engineering)\b",
    r'\b(M\.?B\.?A|Masters? of Business Administration|M\.?C\.?A|Masters? of Computer Applications)\b',
    r'\b(M\.?A|Masters? of Arts|M\.?Com|Masters? of Commerce|M\.?Ed|M\.?Phil|LL\.?M)\b',
    r'\b(Postgraduate|PG)\b',
    
    # Bachelor's degrees & Undergraduate
    r"\b(B\s*\.?\s*Tech|BTECH|Bachelor'?s?\s+of\s+Technology|Bachelors?\s+of\s+Technology|B\s*\.?\s*Technology)\b",
    r"\b(B\.?S|BS|Bachelor'?s?\s+of\s+Science|Bachelors?\s+of\s+Science|B\.?Sc|BSC)\b",
    r"\b(B\.?E|BE|B\.?Eng|BENG|Bachelor'?s?\s+of\s+Engineering|Bachelors?\s+of\s+Engineering)\b",
    r'\b(B\.?B\.?A|Bachelors? of Business Administration|B\.?C\.?A|Bachelors? of Computer Applications)\b',
    r'\b(B\.?A|Bachelors? of Arts|B\.?Com|Bachelors? of Commerce|B\.?Ed|B\.?Pharm|B\.?Arch|LL\.?B)\b',
    r'\b(Undergraduate|UG)\b',

    # Generic degree phrases that appear in many fresher resumes
    r"\bBachelor[’']?s\s+Degree\b",
    r"\bMaster[’']?s\s+Degree\b",
    
    # Associate & Diplomas
    r'\b(Associate Degree|Associate of Science|Associate of Arts|Diploma|PGDM|PGDCA|Post Graduate Diploma)\b',
]

# Fields of study
FIELDS_OF_STUDY = [
    "Computer Science", "Information Technology", "IT", "Software Engineering",
    "Computer Engineering", "Data Science", "Artificial Intelligence", "AI",
    "Machine Learning", "Cybersecurity", "Information Systems",
    "Electrical Engineering", "Electronics", "Mechanical Engineering",
    "Civil Engineering", "Chemical Engineering", "Aerospace Engineering",
    "Biomedical Engineering", "Industrial Engineering",
    "Business Administration", "Business Management", "Finance", "Accounting",
    "Economics", "Marketing", "Human Resources", "HR", "Operations Management",
    "Mathematics", "Statistics", "Physics", "Chemistry", "Biology",
    "Psychology", "Sociology", "Political Science", "History", "English",
    "Communications", "Journalism", "Public Relations",
    "Graphic Design", "Fine Arts", "Architecture", "Music",
    "Medicine", "Nursing", "Pharmacy", "Public Health",
    "Law", "Education", "Library Science",
]

# Educational institutions indicators
INSTITUTION_INDICATORS = [
    r'\b(University|College|Institute|School|Academy)\b',
    r'\b(IIT|IIM|NIT|BITS|MIT|Stanford|Harvard|Oxford|Cambridge)\b',
]

# Degree level hierarchy
DEGREE_LEVELS = {
    'doctorate': [
        'Ph.D', 'PhD', 'Doctor', 'Doctorate', 'Ed.D', 'M.D', 'J.D', 'D.B.A'
    ],
    'masters': [
        'M.S', 'MS', 'M.A', 'MA', 'MBA', 'M.E', 'M.Eng', 'M.Tech',
        'MCA', 'M.Com', 'M.Ed', 'M.Phil', 'MFA', 'LLM', 'MPH', 'MPA',
        'Postgraduate', 'PG'
    ],
    'bachelors': [
        'B.S', 'BS', 'B.A', 'BA', 'B.E', 'B.Eng', 'B.Tech', 'BBA',
        'BCA', 'B.Com', 'B.Ed', 'BFA', 'LLB', 'B.Arch', 'B.Pharm',
        'Undergraduate', 'UG'
    ],
    'associate': ['A.S', 'AS', 'A.A', 'AA', 'AAS'],
    'diploma': ['Diploma', 'PG Diploma', 'PGDM', 'PGDCA'],
    'certificate': ['Certificate', 'Certification'],
}

# Degree normalization mapping
DEGREE_ALIASES = {
    "BTECH": ["BACHELOR OF TECHNOLOGY", "B.TECH", "B TECH", "B. TECHNOLOGY"],
    "MTECH": ["MASTER OF TECHNOLOGY", "M.TECH", "M TECH", "M. TECHNOLOGY"],
    "MCA": ["MASTER OF COMPUTER APPLICATIONS", "M.C.A", "M CA"],
    "MBA": ["MASTER OF BUSINESS ADMINISTRATION", "M.B.A", "M BA"],
    "BCA": ["BACHELOR OF COMPUTER APPLICATIONS", "B.C.A", "B CA"],
    "BSC": ["BACHELOR OF SCIENCE", "B.SC", "B SC", "B.S"],
    "MSC": ["MASTER OF SCIENCE", "M.SC", "M SC", "M.S"],
    "BE": ["BACHELOR OF ENGINEERING", "B.E", "B ENG", "B.ENG"],
    "ME": ["MASTER OF ENGINEERING", "M.E", "M ENG", "M.ENG"],
}

def normalize_degree(degree_name: str) -> str:
    """Normalize a degree name to its common alias."""
    if not degree_name:
        return ""
    upper_name = degree_name.upper().strip()
    for alias, patterns in DEGREE_ALIASES.items():
        if upper_name == alias:
            return alias
        for pattern in patterns:
            if pattern in upper_name:
                return alias
    return upper_name

def extract_qualifications(resume_text: str) -> Dict[str, Any]:
    """
    Extract educational qualifications from resume text.

    Args:
        resume_text: Raw text from resume

    Returns:
        Dictionary containing extracted data
    """
    if not resume_text:
        return {
            "degrees": [],
            "fields": [],
            "institutions": [],
            "highest_degree": None,
            "qualification_text": "",
            "year_of_passing": None
        }

    text_original = resume_text

    # Extract degrees
    degrees = []
    for pattern in DEGREE_PATTERNS:
        matches = re.findall(pattern, text_original, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            cleaned = match.strip()
            if cleaned and cleaned not in degrees:
                degrees.append(cleaned)

    # Fallback: scan for standalone degree strings that the regexes above
    # might miss due to DOCX formatting (e.g. "B.TECH" alone on a line).
    if not degrees:
        standalone_degree_re = re.compile(
            r"(?:^|\s)(B\.?\s*TECH|M\.?\s*TECH|BTECH|MTECH|MCA|MBA|BCA|BBA|"
            r"B\.?E|M\.?E|B\.?SC|M\.?SC|B\.?A|M\.?A|B\.?COM|M\.?COM|"
            r"B\.?ED|M\.?ED|PH\.?D|PGDM|PGDCA)(?:\s|$|[,.])",
            re.IGNORECASE,
        )
        for m in standalone_degree_re.finditer(text_original):
            cleaned = m.group(1).strip()
            if cleaned and cleaned not in degrees:
                degrees.append(cleaned)

    # Extract fields of study
    fields = []
    for field in FIELDS_OF_STUDY:
        if re.search(r'\b' + re.escape(field) + r'\b', text_original, re.IGNORECASE):
            if field not in fields:
                fields.append(field)

    # Extract institutions
    institutions = []
    lines = text_original.split('\n')
    for line in lines:
        for pattern in INSTITUTION_INDICATORS:
            if re.search(pattern, line, re.IGNORECASE):
                cleaned_line = line.strip()
                if 5 < len(cleaned_line) < 200:
                    if cleaned_line not in institutions:
                        institutions.append(cleaned_line)
                break

    # Determine highest degree level
    highest_degree = None
    highest_level = None
    level_order = ['doctorate', 'masters', 'bachelors', 'associate', 'diploma', 'certificate']

    for degree in degrees:
        level = _degree_level_from_text(degree)
        if not level:
            continue
        if highest_level is None or level_order.index(level) < level_order.index(highest_level):
            highest_level = level
            highest_degree = degree

    # If we failed to extract explicit degree strings, try inferring from
    # the Education block / full text.  We scan LINE-BY-LINE rather than
    # passing the whole block because _degree_level_from_text strips all
    # non-alphanumeric chars → on a large block, short patterns like "DBA"
    # or "AAS" appear by coincidence in the concatenated text.
    if highest_level is None:
        education_block = _extract_education_block(text_original)
        fallback_text = education_block if education_block else text_original
        for ln in fallback_text.splitlines():
            cleaned = ln.strip()
            if not cleaned or len(cleaned) > 120:
                continue
            level = _degree_level_from_text(cleaned)
            if level:
                if highest_level is None or level_order.index(level) < level_order.index(highest_level):
                    highest_level = level

    # Ultimate fallback: If no explicit degree degree string found, but valid College/University 
    # was extracted, assume a Bachelor's degree (very common in Indian tech resumes where they 
    # just write "X Engineering College").
    if highest_level is None and institutions:
        for inst in institutions:
            inst_lower = inst.lower()
            if any(keyword in inst_lower for keyword in ['engineering', 'college', 'university', 'institute', 'technology']):
                highest_level = 'bachelors'
                inferred_degree = "Bachelor's Degree (Inferred)"
                if not highest_degree:
                    highest_degree = inferred_degree
                if inferred_degree not in degrees:
                    degrees.append(inferred_degree)
                break

    # Extract graduation year (prefer education section / date ranges)
    grad_year = _extract_graduation_year(text_original)

    # qualification_text for summary display
    qual_text = f"{highest_degree or ''} {f'in {fields[0]}' if fields else ''}".strip()

    return {
        "degrees": degrees[:5],
        "fields": fields[:5],
        "institutions": institutions[:3],
        "highest_degree": highest_degree,
        "highest_level": highest_level,
        "qualification_text": qual_text,
        "year_of_passing": grad_year
    }

def match_qualification(candidate_quals: Dict[str, Any],
                       required_qualifications: Any,  # Now accepts string or list of strings
                       required_years: Optional[Any] = None) -> Dict[str, Any]:
    """
    Match candidate qualifications against requirements.
    Supports multiple degree requirements, levels, synonyms, and specific graduation years.
    Returns the best match found among the required qualifications.
    """
    # Normalize input to a list
    req_qual_list = []
    if isinstance(required_qualifications, str):
        if not required_qualifications or required_qualifications == "None":
            req_qual_list = []
        else:
            req_qual_list = [required_qualifications]
    elif isinstance(required_qualifications, list):
        req_qual_list = [q for q in required_qualifications if q and q != "None"]

    if not req_qual_list or not candidate_quals:
        if not req_qual_list or "None" in req_qual_list:
            return {
                "match_score": 1.0, 
                "matched": True,
                "year_match": True,
                "details": "No specific qualification requirement"
            }
        else:
            return {
                "match_score": 0.0,
                "matched": False,
                "year_match": False,
                "details": "Rejection: No educational degrees detected in resume"
            }

    candidate_degrees = [normalize_degree(d) for d in candidate_quals.get("degrees", [])]
    candidate_level = candidate_quals.get("highest_level")

    # Level Hierarchy
    level_order = ['doctorate', 'masters', 'bachelors', 'associate', 'diploma', 'certificate']
    def get_level(degree_norm):
        # Use robust inference first (handles MTECH/BTECH etc)
        inferred = _degree_level_from_text(degree_norm)
        if inferred:
            return inferred

        for level, keywords in DEGREE_LEVELS.items():
            for kw in keywords:
                if kw.upper() in str(degree_norm).upper():
                    return level
        return None

    best_match_score = 0.0
    best_matched = False
    best_details = f"Required qualifications {', '.join(req_qual_list)} not identified"
    best_req_qual = req_qual_list[0] if req_qual_list else None
    
    # Iterate through all acceptable qualifications to find the best match
    for req_qual in req_qual_list:
        required_norm = normalize_degree(req_qual)
        required_level = get_level(required_norm)
        
        current_score = 0.0
        current_matched = False
        current_details = ""

        # 1. Direct or Synonym Match (e.g. BTech == Bachelor of Technology)
        if required_norm in candidate_degrees:
            current_matched = True
            current_score = 1.0
            current_details = f"Verified {required_norm} qualification"
        
        # 2. Level Hierarchy Match (e.g. Master's covers Bachelor's)
        elif required_level and candidate_level:
            req_idx = level_order.index(required_level)
            cand_idx = level_order.index(candidate_level)
            
            if cand_idx == req_idx:
                # They share a level (e.g., both Masters), but the specific degrees didn't match above.
                # E.g. Candidate has MBA, Requirement is MTech. These are completely different!
                current_matched = False
                current_score = 0.4
                current_details = f"Mismatched degree at same level: {candidate_level.title()} level found, but strict {required_norm} is missing"
            elif cand_idx < req_idx:
                # Overqualified: candidate has a higher degree than required (e.g. Master's vs Bachelor's)
                # Apply a slight penalty to avoid bias toward overqualified candidates
                current_matched = True
                current_score = 0.8  
                current_details = f"Overqualified: {candidate_level.title()} exceeds {required_level.title()} requirement"
            else:
                current_score = 0.3
                current_details = f"Level below requirement: {candidate_level.title()} < {required_level.title()}"
        
        # Special "Any" degree cases
        elif "ANY BACHELOR" in required_norm:
            if candidate_level == 'bachelors':
                current_matched = True
                current_score = 1.0
                current_details = "Matched Bachelor's level requirement exactly"
            elif candidate_level in ['masters', 'doctorate']:
                current_matched = True
                current_score = 0.8
                current_details = "Overqualified: exceeds Bachelor's level requirement"
        elif "ANY MASTER" in required_norm:
            if candidate_level == 'masters':
                current_matched = True
                current_score = 1.0
                current_details = "Matched Master's level requirement exactly"
            elif candidate_level == 'doctorate':
                current_matched = True
                current_score = 0.8
                current_details = "Overqualified: exceeds Master's level requirement"
                
        # Update best match if this is better
        if current_score > best_match_score or (current_score == best_match_score and current_matched):
            best_match_score = current_score
            best_matched = current_matched
            best_details = current_details or f"Required {req_qual} not identified"
            best_req_qual = req_qual
            
            # If we found a perfect match, no need to check others
            if best_match_score == 1.0 and best_matched:
                break

    # 3. Year of Passing Inclusion Logic
    year_match = True
    candidate_year = candidate_quals.get("year_of_passing")
    
    # Standardize required_years into a list
    allowed_years = []
    if isinstance(required_years, (int, float)):
        allowed_years = [int(required_years)]
    elif isinstance(required_years, list):
        allowed_years = [int(y) for y in required_years if str(y).strip().isdigit()]

    if allowed_years and candidate_year:
        if candidate_year not in allowed_years:
            year_match = False
            best_match_score = 0.0
            best_matched = False
            best_details = (f"Rejection: Graduation year {candidate_year} is not in "
                       f"Allowed list ({', '.join(map(str, allowed_years))})")
    elif allowed_years and not candidate_year:
        # Could not detect year — strict mode requires the year to be present and match.
        year_match = False
        best_match_score = 0.0
        best_matched = False
        best_details = ("Rejection: Graduation year not detected (Required: one of "
                   + ", ".join(map(str, allowed_years)) + ")")

    # 4. Final Fallback if no degrees found at all
    if not best_matched and not candidate_quals.get("degrees"):
        # Before giving up, check if highest_level was inferred from the text
        if candidate_quals.get("highest_level"):
            # We inferred a level even though no explicit degree string was captured
            pass  # keep existing match_score / details
        else:
            best_match_score = 0.0
            best_details = "Rejection: No educational degrees detected in resume"

    return {
        "match_score": best_match_score,
        "matched": best_matched,
        "year_match": year_match,
        "details": best_details,
        "candidate_qualification": candidate_quals.get("qualification_text", ""),
        "candidate_year": candidate_year,
        "required_qualification": best_req_qual or "None",
        "required_years": allowed_years
    }
