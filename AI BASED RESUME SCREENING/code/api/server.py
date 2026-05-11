"""
Flask REST API Server for AI Resume Screening System.
Wraps existing core/ and utils/ modules to expose them as HTTP endpoints.
"""

import sys
import os
import re
import io
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps

from flask import Flask, request, jsonify, send_file, g
from flask_cors import CORS

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from supabase_client import supabase
from core.config import SHORTLIST_THRESHOLD, SEMANTIC_WEIGHT, SKILL_WEIGHT, EXPERIENCE_WEIGHT
from core.text_extractor import extract_text
from core.embedding_engine import EmbeddingEngine
from core.skill_extractor import extract_skills, get_default_skills
from core.experience_extractor import extract_experience
from core.qualification_extractor import extract_qualifications, match_qualification
from core.contact_extractor import extract_contact_info
from core.scoring import compute_scores
from core.hybrid_extractor import llm_extraction_fallback, merge_extracted_data
from core.xai_engine_v3 import generate_text_based_xai
from core.communication_engine import generate_email_draft
from core.notification_engine import send_candidate_notifications
from utils.history_store import save_history, load_history, delete_history_record, clear_all_history
from utils.export_utils import export_to_csv

app = Flask(__name__)
CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173"])

# Fallback in-memory session store used only if DB session table is unavailable.
_sessions = {}


def _extract_bearer_token() -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    return auth_header.split(" ", 1)[1].strip()


def _resolve_authenticated_user_id():
    if supabase is None:
        return None, "Supabase is not configured"

    token = _extract_bearer_token()
    if not token:
        return None, "Missing authorization token"

    try:
        user_res = supabase.auth.get_user(token)
        user = getattr(user_res, "user", None)
        user_id = getattr(user, "id", None)
        if not user_id:
            return None, "Invalid or expired token"
        return user_id, None
    except Exception:
        return None, "Invalid or expired token"


def require_auth(fn):
    @wraps(fn)
    def _wrapper(*args, **kwargs):
        user_id, err = _resolve_authenticated_user_id()
        if err:
            status = 503 if "Supabase" in err else 401
            return jsonify({"error": err}), status
        g.user_id = user_id
        return fn(*args, **kwargs)

    return _wrapper


def _get_session(user_id):
    if supabase is not None:
        try:
            res = (
                supabase.table("user_sessions")
                .select("job_data, results")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            data = res.data or {}
            return {
                "job_data": data.get("job_data") or {},
                "results": data.get("results") or []
            }
        except Exception:
            pass

    if user_id not in _sessions:
        _sessions[user_id] = {}
    return _sessions[user_id]


def _set_session(user_id, job_data=None, results=None):
    current = _get_session(user_id)
    payload = {
        "user_id": user_id,
        "job_data": current.get("job_data", {}),
        "results": current.get("results", [])
    }

    if job_data is not None:
        payload["job_data"] = job_data
    if results is not None:
        payload["results"] = results

    if supabase is not None:
        try:
            supabase.table("user_sessions").upsert(payload, on_conflict="user_id").execute()
            return payload
        except Exception:
            pass

    _sessions[user_id] = {
        "job_data": payload.get("job_data", {}),
        "results": payload.get("results", [])
    }
    return payload


def sanitize_jd(text: str) -> str:
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\{[^}]*\}', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---- Health ----
@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/status")
def status():
    return jsonify({
        "supabase_configured": supabase is not None
    })


# ---- Auth ----
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "")
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    if supabase is None:
        return jsonify({"error": "Supabase is not configured"}), 503

    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        return jsonify({
            "user": {
                "id": res.user.id,
                "email": res.user.email
            },
            "session": {
                "access_token": res.session.access_token,
                "refresh_token": res.session.refresh_token
            }
        })
    except Exception as e:
        return jsonify({"error": "Invalid email or password"}), 401


@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email", "")
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if supabase is None:
        return jsonify({"error": "Supabase is not configured"}), 503

    try:
        supabase.auth.sign_up({"email": email, "password": password})
        return jsonify({"message": "Account created successfully"})
    except Exception as e:
        msg = str(e).lower()
        if "already registered" in msg:
            return jsonify({"error": "Email already registered"}), 409
        return jsonify({"error": "Signup failed"}), 400


@app.route("/api/auth/guest", methods=["POST"])
def guest_login():
    return jsonify({"error": "Guest mode is disabled. Please sign in with Supabase."}), 400


# ---- Job Config ----
@app.route("/api/job-config", methods=["POST"])
@require_auth
def save_job_config():
    data = request.json or {}
    user_id = g.user_id

    if supabase is None:
        return jsonify({"error": "Supabase is not configured"}), 503

    job_title = data.get("job_title", "").strip()
    job_description = data.get("job_description", "")
    qualification = data.get("qualification", ["None"])
    year_of_passing = data.get("year_of_passing", [])
    required_experience = data.get("required_experience", 0)
    must_have_skills = data.get("must_have_skills", [])
    good_to_have_skills = data.get("good_to_have_skills", [])

    if not job_title or not job_description:
        return jsonify({"error": "Job title and description required"}), 400

    word_count = len(job_description.split())
    if word_count < 30:
        return jsonify({"error": f"Job description must be at least 30 words (current: {word_count})"}), 400
    if word_count > 2500:
        return jsonify({"error": f"Job description must be at most 2500 words (current: {word_count})"}), 400

    clean_jd = sanitize_jd(job_description)
    if len(clean_jd) < 50:
        return jsonify({"error": "Job description too short after sanitization"}), 400

    job_data = {
        "job_title": job_title,
        "job_description": clean_jd,
        "qualification": qualification,
        "year_of_passing": year_of_passing,
        "required_experience": required_experience,
        "must_have_skills": must_have_skills,
        "good_to_have_skills": good_to_have_skills
    }

    # Save to Supabase
    try:
        job_res = supabase.table("job_configs").insert({
            "user_id": user_id,
            "job_title": job_title,
            "job_description": clean_jd,
            "required_qualification": qualification,
            "required_year_of_passing": year_of_passing,
            "required_experience": required_experience,
            "must_have_skills": must_have_skills,
            "good_to_have_skills": good_to_have_skills
        }).execute()

        if job_res.data:
            job_data["job_id"] = job_res.data[0]["id"]
    except Exception as e:
        print(f"Error saving job config to DB: {e}")
        return jsonify({"error": "Failed to save job config to database"}), 500

    # Store in session
    _set_session(user_id, job_data=job_data)

    return jsonify({"message": "Job configuration saved", "job_data": job_data})


# ---- Resume Processing ----
def _process_single_resume(resume_name, resume_bytes, embedder, jd_embedding,
                            all_potential_skills, job_data):
    """Process a single resume end-to-end (same logic as Streamlit version)."""

    class _BytesFile:
        def __init__(self, data, name):
            self._buf = io.BytesIO(data)
            self.name = name
        def read(self, *a): return self._buf.read(*a)
        def seek(self, *a): return self._buf.seek(*a)
        def tell(self): return self._buf.tell()

    file_obj = _BytesFile(resume_bytes, resume_name)

    text = extract_text(file_obj)
    if not text or not text.strip():
        return {"error": f"Could not extract text from {resume_name}", "resume_name": resume_name}

    resume_embedding = embedder.embed_resume(text)
    if resume_embedding is None:
        return {"error": f"Could not embed resume {resume_name}", "resume_name": resume_name}
    semantic_score = float(jd_embedding @ resume_embedding)

    skills = extract_skills(text, all_potential_skills)
    exp_data = extract_experience(text)
    experience = exp_data["years"]
    projects = exp_data["projects"]

    qualifications = extract_qualifications(text)
    required_qual = job_data.get("qualification", "None")
    required_years = job_data.get("year_of_passing", [])
    qualification_match = match_qualification(qualifications, required_qual, required_years)

    if required_qual and (not isinstance(required_qual, list) or (required_qual != ["None"] and len(required_qual) > 0)):
        if required_qual != "None" and required_qual != [""]:
            if not qualification_match.get("matched"):
                return {
                    "rejected": True,
                    "resume_name": resume_name,
                    "reason": qualification_match.get("details")
                }

    contact_info = extract_contact_info(text)
    heuristic_data = {
        "name": contact_info.get("name"),
        "email": contact_info.get("email"),
        "phone": contact_info.get("phone"),
        "linkedin": contact_info.get("linkedin"),
        "github": contact_info.get("github"),
        "portfolio": contact_info.get("portfolio"),
        "skills": skills,
        "experience": experience,
        "projects": projects,
    }

    if not heuristic_data["name"] or len(heuristic_data["skills"]) < 3:
        llm_data = llm_extraction_fallback(text)
        if llm_data:
            heuristic_data = merge_extracted_data(heuristic_data, llm_data)
            skills = heuristic_data["skills"]
            experience = heuristic_data["experience"]

    candidate_name = heuristic_data["name"] or resume_name

    scores = compute_scores(
        semantic_score,
        set(skills),
        experience,
        job_data,
        resume_text_len=len(text),
        qualification_match=qualification_match
    )

    return {
        "resume_name": candidate_name,
        "resume_filename": resume_name,
        "resume_text": text,
        "email": heuristic_data.get("email"),
        "phone": heuristic_data.get("phone"),
        "linkedin": heuristic_data.get("linkedin"),
        "github": heuristic_data.get("github"),
        "portfolio": heuristic_data.get("portfolio"),
        "skills": skills,
        "experience": experience,
        "projects": heuristic_data.get("projects", []),
        "qualifications": qualifications,
        "qualification_match": qualification_match,
        "scores": scores,
    }


@app.route("/api/process", methods=["POST"])
@require_auth
def process_resumes():
    user_id = g.user_id
    if supabase is None:
        return jsonify({"error": "Supabase is not configured"}), 503

    job_data_str = request.form.get("job_data")

    if not job_data_str:
        session = _get_session(user_id)
        job_data = session.get("job_data")
        if not job_data:
            return jsonify({"error": "No job configuration found"}), 400
    else:
        job_data = json.loads(job_data_str)

    files = request.files.getlist("resumes")
    if not files:
        return jsonify({"error": "No resumes uploaded"}), 400

    embedder = EmbeddingEngine()
    jd_embedding = embedder.embed_query(job_data["job_description"])

    all_potential_skills = list(set(
        job_data.get("must_have_skills", []) +
        job_data.get("good_to_have_skills", []) +
        get_default_skills()
    ))

    # Deduplication
    seen_hashes = set()
    unique_resumes = []
    duplicate_names = []
    for f in files:
        content = f.read()
        f.seek(0)
        file_hash = hashlib.md5(content).hexdigest()
        if file_hash in seen_hashes:
            duplicate_names.append(f.filename)
        else:
            seen_hashes.add(file_hash)
            unique_resumes.append((f.filename, content))

    total = len(unique_resumes)
    if total == 0:
        return jsonify({"error": "All uploaded files were duplicates"}), 400

    results = []
    rejected = []
    errors = []

    MAX_WORKERS = min(4, total)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(
                _process_single_resume,
                name, content, embedder, jd_embedding,
                all_potential_skills, job_data
            ): name
            for name, content in unique_resumes
        }

        for future in as_completed(future_map):
            resume_name = future_map[future]
            try:
                outcome = future.result()
                if outcome is None:
                    continue
                elif outcome.get("error"):
                    errors.append({"name": outcome["resume_name"], "error": outcome.get("error", "Processing error")})
                elif outcome.get("rejected"):
                    rejected.append({"name": outcome["resume_name"], "reason": outcome.get("reason", "")})
                else:
                    results.append(outcome)
            except Exception as exc:
                errors.append({"name": resume_name, "error": str(exc)})

    # Auto-save to history
    threshold = SHORTLIST_THRESHOLD
    shortlisted = [r for r in results if r["scores"]["final_score"] >= threshold]
    history_full_results = list(results)
    history_full_results.extend([
        {
            "resume_name": item.get("name", "Unknown Resume"),
            "status": "rejected",
            "rejection_reason": item.get("reason", "")
        }
        for item in rejected
    ])
    history_full_results.extend([
        {
            "resume_name": item.get("name", "Unknown Resume"),
            "status": "error",
            "error": item.get("error", "Unknown processing error")
        }
        for item in errors
    ])
    history_status = {"saved": False, "reason": "not_attempted"}
    try:
        history_status = save_history(job_data, threshold, shortlisted, all_results=history_full_results, user_id=user_id)
    except Exception as e:
        print(f"Auto-save failed: {e}")
        history_status = {"saved": False, "reason": str(e)}

    # Serialize results (remove non-JSON-serializable fields)
    serializable_results = []
    for r in results:
        sr = {k: v for k, v in r.items() if k != "resume_embedding"}
        serializable_results.append(sr)

    _set_session(user_id, job_data=job_data, results=serializable_results)

    return jsonify({
        "total": total,
        "passed": len(results),
        "rejected": rejected,
        "errors": errors,
        "duplicates": duplicate_names,
        "results": serializable_results,
        "history": history_status
    })


# ---- Results ----
@app.route("/api/results", methods=["GET"])
@require_auth
def get_results():
    user_id = g.user_id
    session = _get_session(user_id)
    results = session.get("results", [])
    job_data = session.get("job_data", {})

    serializable = []
    for r in results:
        sr = {k: v for k, v in r.items() if k != "resume_embedding"}
        serializable.append(sr)

    return jsonify({
        "results": serializable,
        "job_data": job_data,
        "config": {
            "shortlist_threshold": SHORTLIST_THRESHOLD,
            "semantic_weight": SEMANTIC_WEIGHT,
            "skill_weight": SKILL_WEIGHT,
            "experience_weight": EXPERIENCE_WEIGHT
        }
    })


@app.route("/api/session", methods=["POST"])
@require_auth
def set_session_data():
    data = request.json or {}
    user_id = g.user_id

    session = _get_session(user_id)
    next_job_data = session.get("job_data", {})
    next_results = session.get("results", [])
    if "job_data" in data:
        next_job_data = data.get("job_data") or {}
    if "results" in data:
        next_results = data.get("results") or []

    _set_session(user_id, job_data=next_job_data, results=next_results)

    return jsonify({"message": "Session data updated"})

@app.route("/api/results/export-csv", methods=["POST"])
@require_auth
def export_csv_route():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    candidates = data.get("candidates", [])
    job_data = data.get("job_data", {})
    
    try:
        csv_str = export_to_csv(candidates, job_data)
        
        mem = io.BytesIO()
        mem.write(csv_str.encode("utf-8"))
        mem.seek(0)
        
        job_title = job_data.get("job_title", "Shortlisted").strip()
        safe_title = re.sub(r'[^a-zA-Z0-9]', '_', job_title)
        safe_title = re.sub(r'_+', '_', safe_title).strip('_')
        dl_name = f"{safe_title}_Candidates.csv"
        
        return send_file(
            mem,
            mimetype="text/csv",
            as_attachment=True,
            download_name=dl_name
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/api/results/xai", methods=["POST"])
@require_auth
def get_xai():
    try:
        data = request.json
        job_data = data.get("job_data", {})
        candidate = data.get("candidate", {})
        
        if not candidate:
            return jsonify({"error": "No candidate data provided"}), 400
        
        analysis = generate_text_based_xai(job_data, candidate)
        
        if not analysis:
            return jsonify({"error": "Failed to generate analysis"}), 500
        
        # Return structured analysis + text_summary for backward compat
        return jsonify({
            "analysis": analysis,
            "explanation": analysis.get("text_summary", "")
        })
    except Exception as e:
        print(f"XAI generation error: {str(e)}")
        return jsonify({"error": f"XAI generation failed: {str(e)}"}), 500


@app.route("/api/results/email-draft", methods=["POST"])
@require_auth
def get_email_draft():
    data = request.json
    candidate = data.get("candidate", {})
    job_data = data.get("job_data", {})
    draft_type = data.get("draft_type", "rejection")
    draft = generate_email_draft(candidate, job_data, draft_type)
    return jsonify({"draft": draft})


@app.route("/api/results/send-notifications", methods=["POST"])
@require_auth
def send_notifications():
    data = request.json or {}
    candidates = data.get("candidates", [])
    job_data = data.get("job_data", {})
    threshold = float(data.get("threshold", SHORTLIST_THRESHOLD) or SHORTLIST_THRESHOLD)

    if not candidates:
        return jsonify({"error": "No candidates provided"}), 400

    result = send_candidate_notifications(candidates, job_data, threshold)

    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)


# ---- History ----
@app.route("/api/history", methods=["GET"])
@require_auth
def get_history():
    user_id = g.user_id
    history = load_history(user_id=user_id)

    # Sanitize: remove full_results for the list view (too large)
    light_history = []
    for record in history:
        r = {k: v for k, v in record.items() if k != "full_results"}
        r["has_full_results"] = bool(record.get("full_results"))
        light_history.append(r)

    return jsonify({"history": light_history})


@app.route("/api/history/<history_id>/results", methods=["GET"])
@require_auth
def get_history_results(history_id):
    user_id = g.user_id
    history = load_history(user_id=user_id)
    for record in history:
        if str(record.get("id")) == str(history_id):
            return jsonify({
                "job_data": {
                    "job_title": record.get("job_title", ""),
                    "qualification": record.get("qualification", ""),
                    "year_of_passing": record.get("year_of_passing", []),
                    "required_experience": record.get("required_experience", 0),
                    "must_have_skills": record.get("must_have_skills", []),
                    "good_to_have_skills": record.get("good_to_have_skills", []),
                    "job_description": record.get("job_description", ""),
                },
                "results": record.get("full_results", []),
                "threshold": record.get("threshold", SHORTLIST_THRESHOLD)
            })
    return jsonify({"error": "Record not found"}), 404


@app.route("/api/history/<history_id>", methods=["DELETE"])
@require_auth
def delete_history(history_id):
    user_id = g.user_id
    delete_history_record(history_id, user_id=user_id)
    return jsonify({"message": "Record deleted"})


@app.route("/api/history/clear", methods=["DELETE"])
@require_auth
def clear_history():
    user_id = g.user_id
    clear_all_history(user_id=user_id)
    return jsonify({"message": "All history cleared"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
