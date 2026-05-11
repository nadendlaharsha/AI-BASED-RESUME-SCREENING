"""
Experience Extractor Module (Revised)

This module implements a robust, multi-pass pipeline for extracting professional 
experience years from resume text. It uses structural mapping, unified date parsing,
and deep role verification to ensure maximum accuracy and strict project exclusion.
"""

import re
from datetime import datetime
from typing import List, Dict, Optional, Any

# --- Configuration & Patterns ---
CURRENT_YEAR = datetime.now().year
CURRENT_MONTH = datetime.now().month

MONTH_MAP = {
    "jan": 1, "january": 1, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4,
    "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# Section Category Patterns
SECTION_MAP = {
    "experience": [
        r"(?:^|\n)\s*(work\s*experience|professional\s*experience|employment\s*history"
        r"|experience|work\s*history|career\s*history|employment|professional\s*summary)\s*[:\n]",
    ],
    "projects": [
        r"(?:^|\n)\s*(academic\s*projects?|personal\s*projects?|projects?|key\s*projects?|notable\s*projects?"
        r"|independent\s*projects?|portfolio|github\s*projects?|technical\s*projects?|mini\s*projects?"
        r"|capstone\s*projects?|curriculum\s*projects?|academic\s*portfolio)\s*[:\n]",
    ],
    "education": [
        r"(?:^|\n)\s*(education|academic\s*background|academic\s*qualifications?"
        r"|educational\s*qualifications?|qualifications?|academic\s*profile)\s*[:\n]",
    ]
}

# Indicators for Role Verification
JOB_TITLE_PATTERNS = [
    r"\b(software|web|mobile|frontend|backend|fullstack|full[\s-]?stack)\s*(engineer|developer)\b",
    r"\b(senior|junior|lead|staff|principal|associate)\s*(engineer|developer|analyst|consultant)\b",
    r"\b(data|ml|machine\s*learning|ai)\s*(scientist|engineer|analyst)\b",
    r"\b(devops|sre|cloud|platform)\s*engineer\b",
    r"\b(qa|test|quality)\s*(engineer|analyst|lead)\b",
    r"\b(product|project|program|engineering)\s*manager\b",
    r"\b(business|systems?|data)\s*analyst\b",
    r"\b(technical|solution)\s*architect\b",
    r"\bconsultant\b", r"\bmanager\b", r"\bdirector\b", r"\bintern\b",
]

COMPANY_INDICATORS = [
    r"\b(pvt\.?|private)\s*(ltd\.?|limited)\b",
    r"\b(ltd\.?|limited|inc\.?|incorporated|corp\.?|corporation|llc|llp)\b",
    r"\b(technologies|solutions|systems|services|consulting|software|infotech|infosys|"
    r"tcs|wipro|cognizant|accenture|google|microsoft|amazon|meta)\b",
]

PROJECT_STOPWORDS = [
    "mini project", "academic project", "major project", "minor project",
    "capstone", "curriculum", "semester", "college project", "self-study",
    "coursework", "assignment", "thesis", "dissertation", "training project"
]

# --- Helper Functions ---

def _parse_month(month_str: str) -> int:
    if not month_str: return 6
    return MONTH_MAP.get(month_str.strip().lower()[:3], 6)

def _parse_year(year_str: str) -> Optional[int]:
    if not year_str: return None
    try:
        year = int(year_str.strip()[-4:]) # Handle potential YYYY or YY
        if year < 100:
            year += 2000 if year <= (CURRENT_YEAR % 100) + 2 else 1900
        if 1970 <= year <= CURRENT_YEAR + 5: return year
    except Exception: pass
    return None

def _to_decimal(year: int, month: int = 6) -> float:
    return year + (month - 1) / 12.0

# --- Structural Mapping ---

def map_resume_structure(text: str) -> List[Dict[str, Any]]:
    """Segment resume into logical blocks based on headers."""
    text_lower = text.lower()
    headers = []
    
    for cat, patterns in SECTION_MAP.items():
        for p in patterns:
            for match in re.finditer(p, text_lower):
                headers.append({
                    "type": cat,
                    "start": match.start(),
                    "content_start": match.end(),
                    "title": match.group(0).strip()
                })
    
    headers.sort(key=lambda x: x["start"])
    
    # Define blocks
    blocks = []
    if not headers:
        # If no headers, treat whole text as general (might be experience)
        blocks.append({"type": "general", "content": text, "start": 0})
        return blocks

    # Handle pre-header text (usually contact/summary)
    if headers[0]["start"] > 10:
        blocks.append({"type": "header", "content": text[:headers[0]["start"]], "start": 0})

    for i, h in enumerate(headers):
        start = h["content_start"]
        end = headers[i+1]["start"] if i + 1 < len(headers) else len(text)
        blocks.append({
            "type": h["type"],
            "content": text[start:end],
            "start": start
        })
        
    return blocks

# --- Unified Date Parser ---

def extract_date_intervals(text: str) -> List[Dict[str, Any]]:
    """A highly robust, multi-format date extractor."""
    intervals = []
    text_lower = text.lower()
    
    present_pattern = r"(?:present|current|now|till\s*date|ongoing|continue|active)"
    month_names = "|".join(MONTH_MAP.keys())
    
    date_patterns = [
        # MMM YYYY - MMM YYYY (standard)
        rf"({month_names})\.?\s*(\d{{2,4}})\s*[\-–—to]+\s*({month_names}|{present_pattern})\.?\s*(\d{{2,4}})?",
        # MM/YYYY - MM/YYYY (numeric)
        r"(\d{1,2})[/\-](\d{2,4})\s*[\-–—to]+\s*(\d{1,2}|" + present_pattern + r")[/\-]?(\d{2,4})?",
        # YYYY - YYYY (year only)
        r"\b(20\d{2})\s*[\-–—to]+\s*(20\d{2}|" + present_pattern + r")\b",
    ]
    
    for p in date_patterns:
        for match in re.finditer(p, text_lower):
            try:
                # Handle grouping logic (highly variant based on patterns)
                groups = match.groups()
                start_m, start_y, end_m, end_y = 6, None, CURRENT_MONTH, CURRENT_YEAR
                
                if len(groups) == 4: # MMM YYYY or MM/YYYY
                    if groups[0].isdigit(): # Numeric
                        start_m, start_y = int(groups[0]), _parse_year(groups[1])
                    else: # String month
                        start_m, start_y = _parse_month(groups[0]), _parse_year(groups[1])
                    
                    if not re.search(present_pattern, groups[2]):
                        if groups[2].isdigit(): # Numeric
                            end_m = int(groups[2])
                            end_y = _parse_year(groups[3]) if groups[3] else start_y
                        else: # String month
                            end_m = _parse_month(groups[2])
                            end_y = _parse_year(groups[3]) if groups[3] else start_y
                            
                elif len(groups) == 2: # Year only
                    start_m, start_y = 1, _parse_year(groups[0])
                    if not re.search(present_pattern, groups[1]):
                        end_m, end_y = 12, _parse_year(groups[1])
                
                if start_y and end_y and start_y <= end_y:
                    start_dec = _to_decimal(start_y, start_m)
                    end_dec = _to_decimal(end_y, end_m)
                    if 0.1 <= (end_dec - start_dec) <= 40:
                        intervals.append({
                            "range": (start_dec, end_dec),
                            "pos": match.start(),
                            "text": match.group(0)
                        })
            except Exception: continue
            
    return intervals

def is_professional_role(context: str, block_type: str) -> bool:
    """Validate if a date match represents a professional job/internship."""
    context_lower = context.lower()
    
    # 1. Block Type check
    if block_type == "projects": return False
    
    # 2. Strict Project Stopwords
    for word in PROJECT_STOPWORDS:
        if word in context_lower:
            # Internship exception
            if "intern" not in context_lower:
                return False
                
    # 3. Positive Indicators (Job titles or companies)
    has_title = any(re.search(p, context_lower) for p in JOB_TITLE_PATTERNS)
    has_company = any(re.search(p, context_lower) for p in COMPANY_INDICATORS)
    is_intern = "intern" in context_lower or "internship" in context_lower
    
    # Experience section grants a boost
    if block_type == "experience":
        return True # Trust sectioning primarily
        
    # Education section must be verified
    if block_type == "education":
        return (has_title or has_company) and is_intern
        
    # General text requires both title/company OR internship
    return (has_title and has_company) or is_intern

# --- Project Detail Extraction ---

def _extract_project_details(content: str) -> List[str]:
    """Extract individual project items from project section content."""
    # Split by common project delimiters: bullet points, newlines with bold text, etc.
    raw_projects = re.split(r'\n(?:\s*[•\-\*]\s*|\s*\d+\.\s*|(?=\*\*))', content)
    projects = []
    
    for p in raw_projects:
        clean_p = p.strip()
        if not clean_p: continue
        
        # Take the first line as title/summary if it's long
        lines = clean_p.split('\n')
        if lines:
            title = lines[0].strip(' *:-')
            if len(title) > 3:
                projects.append(title)
                
    return projects[:5] # Return top 5 projects

# --- Main Logic ---

def extract_experience(text: str) -> Dict[str, Any]:
    """Main pipeline for experience calculation and project extraction."""
    if not text or not text.strip(): 
        return {"years": 0.0, "projects": []}
    
    blocks = map_resume_structure(text)
    all_valid_intervals = []
    projects_list = []
    
    for block in blocks:
        # 1. Handle Project Extraction separately
        if block["type"] == "projects":
            projects_list.extend(_extract_project_details(block["content"]))
            
        # 2. Extract dates for experience calculation
        block_dates = extract_date_intervals(block["content"])
        
        for date_match in block_dates:
            # Get 300 chars of context around the date match in block content
            pos = date_match["pos"]
            start_ctx = max(0, pos - 150)
            end_ctx = min(len(block["content"]), pos + 150)
            context = block["content"][start_ctx:end_ctx]
            
            if is_professional_role(context, block["type"]):
                all_valid_intervals.append(date_match["range"])
                
    # Deduplicate projects
    projects_list = list(set(projects_list))
    
    if not all_valid_intervals:
        # Fallback to explicit extraction if no intervals found
        fallback_yrs = _fallback_explicit(text)
        return {"years": fallback_yrs, "projects": projects_list}
        
    # Merge overlaps
    sorted_ivs = sorted(all_valid_intervals)
    if not sorted_ivs: 
        return {"years": 0.0, "projects": projects_list}
    
    merged = [sorted_ivs[0]]
    for start, end in sorted_ivs[1:]:
        curr_start, curr_end = merged[-1]
        if start <= curr_end + 0.3: # Allow 4 months gap
            merged[-1] = (curr_start, max(curr_end, end))
        else:
            merged.append((start, end))
            
    total = sum(e - s for s, e in merged)
    return {
        "years": round(min(total, 45), 1),
        "projects": projects_list
    }

def _fallback_explicit(text: str) -> float:
    """Last resort: look for 'X years of experience' statements."""
    text_lower = text.lower()
    pattern = r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?(?:experience|exp|work)"
    matches = re.findall(pattern, text_lower)
    if matches:
        try: return round(max(float(m) for m in matches), 1)
        except Exception: pass
    return 0.0
