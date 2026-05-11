import json
from groq import Groq
from core.config import GROQ_API_KEY, LLM_MODEL

def llm_extraction_fallback(text: str) -> dict:
    """
    Uses Llama-3 to extract structured data from resume text when heuristics fail.
    """
    api_key = GROQ_API_KEY
    if not api_key:
        return {}

    try:
        client = Groq(api_key=api_key)
        
        prompt = f"""
        Extract the following information from the resume text provided below.
        Return ONLY a valid JSON object. Do not include any preamble or explanation.
        
        JSON Keys:
        - name: Full Name of the candidate
        - email: Email address
        - phone: Phone number
        - skills: List of technical skills
        - experience_years: Estimated years of professional experience (float)
        - top_projects: List of top 2 projects
        - education: List of degrees or certifications
        
        Resume Text:
        ---
        {text[:4000]}
        ---
        """
        
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional resume parser. Return raw JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        print(f"LLM Extraction Error: {e}")
        return {}

def merge_extracted_data(heuristic_data: dict, llm_data: dict) -> dict:
    """
    Merges heuristic data with LLM data, preferring LLM data for missing fields.
    """
    merged = heuristic_data.copy()
    
    # If heuristic failed to find name, use LLM
    if not merged.get("name") or merged.get("name") == "N/A":
        merged["name"] = llm_data.get("name")
    
    # If heuristic found few skills, add LLM skills
    if len(merged.get("skills", [])) < 3 and llm_data.get("skills"):
        merged["skills"] = list(set(merged.get("skills", []) + llm_data.get("skills")))
        
    # Experience fallback
    if merged.get("experience", 0) <= 0 and llm_data.get("experience_years"):
        merged["experience"] = llm_data.get("experience_years")
        
    # Projects fallback
    if not merged.get("projects") and llm_data.get("top_projects"):
        merged["projects"] = llm_data.get("top_projects")

    # Email/Phone fallbacks
    if not merged.get("email"): merged["email"] = llm_data.get("email")
    if not merged.get("phone"): merged["phone"] = llm_data.get("phone")
        
    return merged
