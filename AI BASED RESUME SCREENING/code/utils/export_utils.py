"""
Export utilities for resume screening results
Allows exporting to CSV, PDF reports, and JSON formats
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict


def export_to_csv(shortlisted_candidates: List[Dict], job_data: Dict) -> str:
    """
    Export shortlisted candidates to CSV format
    
    Returns:
        CSV content as string
    """
    data = []
    for idx, candidate in enumerate(shortlisted_candidates, 1):
        scores = candidate.get("scores", {})
        row = {
            "Rank": idx,
            "Candidate_Name": candidate.get("resume_name", f"Candidate_{idx}"),
            "Email": candidate.get("email", ""),
            # Force Excel to treat phone as string to avoid scientific notation (e.g. 9.12E+10)
            "Phone_Contact": f'="{candidate.get("phone")}"' if candidate.get("phone") else "",
            "Final_Score": scores.get("final_score", 0),
            "Semantic_Score": scores.get("semantic_score", 0),
            "Skill_Score": scores.get("skill_score", 0),
            "Experience_Score": scores.get("experience_score", 0),
            "Experience_Years": candidate.get("experience", 0),
            "Matched_Skills": ", ".join(scores.get("matched_skills", [])),
            "Missing_Skills": ", ".join(scores.get("missing_skills", [])),
            "Matched_Skills_Count": len(scores.get("matched_skills", [])),
            "Missing_Skills_Count": len(scores.get("missing_skills", [])),
            "Confidence": scores.get("confidence", 0),
            "LinkedIn": candidate.get("linkedin", ""),
            "GitHub": candidate.get("github", ""),
            "Portfolio": candidate.get("portfolio", ""),
            "Job_Title": job_data.get("job_title", ""),
            "Screening_Date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        data.append(row)
    
    if not data:
        # Return empty dataframe with correct columns
        columns = ["Rank", "Candidate_Name", "Email", "Phone_Contact", "Final_Score", "Semantic_Score", 
                   "Skill_Score", "Experience_Score", "Experience_Years", "Matched_Skills", "Missing_Skills", 
                   "Matched_Skills_Count", "Missing_Skills_Count", "Confidence", "LinkedIn", "GitHub", "Portfolio", "Job_Title", "Screening_Date"]
        df = pd.DataFrame(columns=columns)
    else:
        df = pd.DataFrame(data)
    
    return df.to_csv(index=False)
