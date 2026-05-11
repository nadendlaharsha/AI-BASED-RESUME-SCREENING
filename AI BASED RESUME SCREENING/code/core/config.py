import json
import os

def load_config():
    """Load configuration from JSON file or environment."""
    config_path = os.path.join("data", "config.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _get_groq_api_key(config: dict) -> str:
    """
    Securely resolve GROQ_API_KEY in priority order:
    1. OS environment variable
    2. config.json (fallback)
    """
    # 1. Environment variable (works for Flask)
    key = os.environ.get("GROQ_API_KEY")
    if key:
        return key

    # 2. config.json fallback
    return config.get("GROQ_API_KEY", "")

_config = load_config()
_weights = _config.get("weights", {"semantic": 0.5, "skill": 0.3, "experience": 0.2})
_thresholds = _config.get("thresholds", {"shortlist": 0.65})
_default_penalties = {
    "must_have_penalty_max": 0.16,
    "experience_penalty_per_year": 0.02,
    "experience_penalty_max": 0.10,
    "semantic_penalty_threshold": 0.18,
    "semantic_penalty_value": 0.05,
    "total_penalty_max": 0.20
}
_penalties = _config.get("penalties", _default_penalties)
_penalty_profiles = _config.get("penalty_profiles", {})
_active_penalty_profile = _config.get("active_penalty_profile")

if _active_penalty_profile and isinstance(_penalty_profiles, dict):
    profile_values = _penalty_profiles.get(_active_penalty_profile)
    if isinstance(profile_values, dict):
        merged = dict(_default_penalties)
        merged.update(_penalties)
        merged.update(profile_values)
        _penalties = merged

SEMANTIC_WEIGHT = _weights.get("semantic", 0.5)
SKILL_WEIGHT = _weights.get("skill", 0.3)
EXPERIENCE_WEIGHT = _weights.get("experience", 0.2)

SHORTLIST_THRESHOLD = _thresholds.get("shortlist", 0.65)

MUST_HAVE_PENALTY_MAX = _penalties.get("must_have_penalty_max", 0.16)
EXPERIENCE_PENALTY_PER_YEAR = _penalties.get("experience_penalty_per_year", 0.02)
EXPERIENCE_PENALTY_MAX = _penalties.get("experience_penalty_max", 0.10)
SEMANTIC_PENALTY_THRESHOLD = _penalties.get("semantic_penalty_threshold", 0.18)
SEMANTIC_PENALTY_VALUE = _penalties.get("semantic_penalty_value", 0.05)
TOTAL_PENALTY_MAX = _penalties.get("total_penalty_max", 0.20)

# LLM Configurations for Llama-3 Alignment
LLM_MODEL = "llama-3.3-70b-versatile"
GROQ_API_KEY = _get_groq_api_key(_config)
