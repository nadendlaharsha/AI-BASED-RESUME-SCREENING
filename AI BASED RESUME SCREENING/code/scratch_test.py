import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.qualification_extractor import match_qualification, normalize_degree, extract_qualifications

candidate_quals = {
    'degrees': ['B.TECH', "Bachelor's Degree (Inferred)"],
    'fields': ['Computer Science'],
    'institutions': ['SOME ENGINEERING COLLEGE'],
    'highest_degree': 'B.TECH',
    'highest_level': 'bachelors',
    'qualification_text': 'B.TECH in Computer Science',
    'year_of_passing': 2026
}

req_qual = ["MTECH"]

res = match_qualification(candidate_quals, req_qual)
print(res)
