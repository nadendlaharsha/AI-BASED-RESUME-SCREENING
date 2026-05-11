import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.qualification_extractor import match_qualification, normalize_degree, extract_qualifications

def bypass_check(required_qual, qualification_match):
    print(f"Testing required_qual={required_qual}")
    if required_qual and required_qual != "None":
        if not qualification_match.get("matched"):
            return {"rejected": True, "reason": qualification_match.get("details")}
    return {"rejected": False}

test_matches = [
    {"matched": False, "details": "Below req"},
]

for required_qual in [["MTech"], ["None"], "MTech", "None", [], None, ""]:
    for match in test_matches:
        res = bypass_check(required_qual, match)
        print(f"  -> {repr(res)}")
