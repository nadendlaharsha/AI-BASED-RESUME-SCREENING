"""
Communication Engine Module

Generates personalized candidate communication drafts (rejections/next-steps)
using LLM based on screening performance.
"""

import os
from typing import Dict, Any
from groq import Groq
from core.config import LLM_MODEL

def generate_email_draft(
    candidate_data: Dict[str, Any],
    job_data: Dict[str, Any],
    email_type: str = "rejection"
) -> str:
    """
    Generate a personalized email draft for a candidate.
    
    Args:
        candidate_data: Dictionary containing candidate name, score, match details, etc.
        job_data: Dictionary containing job title and company info.
        email_type: 'rejection' or 'next_steps'
    """
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    
    candidate_name = candidate_data.get("resume_name", "Candidate")
    job_title = job_data.get("job_title", "Position")
    
    if email_type == "next_steps":
        prompt = f"""
        Act as a professional Recruiter. Write a warm, encouraging 'Next Steps' email to a candidate.
        
        Candidate: {candidate_name}
        Position: {job_title}
        Key Strengths Found: {', '.join(candidate_data.get('scores', {}).get('matched_skills', [])[:3])}
        Match Confidence: {candidate_data.get('scores', {}).get('final_score', 0):.0%}
        
        Requirements:
        1. Professional and exciting tone.
        2. Mention specific strengths identified.
        3. Keep it under 150 words.
        4. Include placeholders for [Time Slot]. Sign off as 'The Hiring Team'.
        
        Output only the email content.
        """
    else:
        prompt = f"""
        Act as a professional and empathetic Recruiter. Write a polite 'Rejection' email.
        
        Candidate: {candidate_name}
        Position: {job_title}
        Missing Skills/Gaps: {', '.join(candidate_data.get('scores', {}).get('missing_skills', [])[:3])}
        
        Requirements:
        1. Empathic, respectful, but clear.
        2. Briefly mention that we prioritized candidates with specific skill alignment.
        3. Do NOT move to interview.
        4. Keep it under 120 words.
        5. Sign off as 'The Hiring Team'.
        
        Output only the email content without any subject line or preamble.
        """

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a professional recruitment communication assistant."},
                {"role": "user", "content": prompt}
            ],
            model=LLM_MODEL,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating draft: {str(e)}"
