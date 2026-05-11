import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.qualification_extractor import extract_qualifications, match_qualification

text = """
Bhuvanesh
Phone: 1234567890
Email: bhuvi@example.com

EDUCATION
B.Tech in Computer Science
XYZ College of Engineering, 2024
"""

job_data = {
    "qualification": ["MTech"]
}

quals = extract_qualifications(text)
print("Extracted Quals:")
print(json.dumps(quals, indent=2))

match = match_qualification(quals, job_data["qualification"])
print("Match result:")
print(json.dumps(match, indent=2))
