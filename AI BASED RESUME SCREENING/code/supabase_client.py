import os
from dotenv import load_dotenv
from supabase import create_client

# Automatically load environment variables from a .env file if it exists
load_dotenv()

supabase = None
try:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")

    # Removed Streamlit fallback; keys must be in env vars.

    if url and key:
        supabase = create_client(url, key)
except Exception:
    supabase = None
