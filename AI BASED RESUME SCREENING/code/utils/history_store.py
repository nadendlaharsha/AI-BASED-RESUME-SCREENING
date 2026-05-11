from datetime import datetime
import time
from supabase_client import supabase


def _to_json_safe(value):
    """Recursively convert values into JSON-serializable Python primitives."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_json_safe(v) for v in value]

    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            pass

    return str(value)


def _execute_with_retry(operation, attempts=3, delay_seconds=0.6):
    """Retry transient database operations a few times before failing."""
    last_error = None
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(delay_seconds)
    raise last_error

def save_history(job_data, threshold, shortlisted_candidates, all_results=None, user_id=None):
    """Save screening history to Supabase only."""
    if user_id is None or user_id == "guest" or supabase is None:
        return {"saved": False, "reason": "invalid_user_or_supabase_unavailable"}

    try:
        history_payload = {
            "user_id": user_id,
            "job_title": job_data["job_title"],
            "job_config_id": job_data.get("job_id"),
            "threshold": threshold,
            "shortlisted_count": len(shortlisted_candidates),
            "job_snapshot": {
                "job_title": job_data.get("job_title", ""),
                "qualification": job_data.get("qualification", ""),
                "year_of_passing": job_data.get("year_of_passing", []),
                "required_experience": job_data.get("required_experience", 0),
                "must_have_skills": job_data.get("must_have_skills", []),
                "good_to_have_skills": job_data.get("good_to_have_skills", []),
                "job_description": job_data.get("job_description", "")
            },
            "full_results": _sanitize_results_for_json(all_results)
        }

        # Prefer rich insert, but gracefully fall back for older schemas.
        try:
            history_res = _execute_with_retry(
                lambda: supabase.table("screening_history").insert(history_payload).execute()
            )
        except Exception:
            fallback_payload = {
                "user_id": user_id,
                "job_title": job_data.get("job_title", "Untitled Job"),
                "job_config_id": job_data.get("job_id"),
                "threshold": threshold,
                "shortlisted_count": len(shortlisted_candidates),
            }
            history_res = _execute_with_retry(
                lambda: supabase.table("screening_history").insert(fallback_payload).execute()
            )

        if not history_res.data:
            return {"saved": False, "reason": "history_insert_empty_response"}

        history_id = history_res.data[0]["id"]
        saved_candidates = 0
        failed_candidates = 0

        for candidate in shortlisted_candidates:
            safe_name = candidate.get("resume_name", "Unknown Candidate").replace(".pdf", "")
            safe_email = candidate.get("email") or ""
            safe_phone = candidate.get("phone") or ""
            safe_score = float(candidate.get("scores", {}).get("final_score", 0.0) or 0.0)

            try:
                raw_emb = candidate.get("resume_embedding")
                emb_list = raw_emb.tolist() if hasattr(raw_emb, "tolist") else raw_emb

                supabase.table("shortlisted_candidates").insert({
                    "history_id": history_id,
                    "candidate_name": safe_name,
                    "candidate_email": safe_email[:250],
                    "candidate_phone": safe_phone[:50],
                    "final_score": safe_score,
                    "embedding": emb_list,
                    "linkedin": candidate.get("linkedin", "")[:300],
                    "github": candidate.get("github", "")[:300],
                    "portfolio": candidate.get("portfolio", "")[:300]
                }).execute()
                saved_candidates += 1
            except Exception as inner_e:
                print(f"Embedding insert failed: {inner_e}. Falling back to basic insert.")
                try:
                    _execute_with_retry(
                        lambda: supabase.table("shortlisted_candidates").insert({
                            "history_id": history_id,
                            "candidate_name": safe_name,
                            "candidate_email": safe_email[:250],
                            "candidate_phone": safe_phone[:50],
                            "final_score": safe_score
                        }).execute()
                    )
                    saved_candidates += 1
                except Exception as basic_insert_error:
                    print(f"Basic candidate insert failed: {basic_insert_error}")
                    failed_candidates += 1
        return {
            "saved": True,
            "history_id": history_id,
            "saved_candidates": saved_candidates,
            "failed_candidates": failed_candidates
        }
    except Exception as e:
        print(f"Error saving history to database: {e}")
        return {"saved": False, "reason": str(e)}


def _sanitize_results_for_json(results):
    """Remove numpy arrays and other non-JSON-serializable objects from results."""
    if not results:
        return results
    sanitized = []
    for r in results:
        sr = {}
        for k, v in r.items():
            if k == "resume_embedding":
                continue  # Skip numpy arrays
            sr[k] = _to_json_safe(v)
        sanitized.append(sr)
    return sanitized


def load_history(user_id=None):
    """Load screening history from Supabase only."""
    if user_id is None or user_id == "guest" or supabase is None:
        return []
    try:
        try:
            history_res = (
                supabase.table("screening_history")
                .select("id, job_config_id, job_title, threshold, shortlisted_count, created_at, full_results, job_snapshot")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
        except Exception:
            history_res = (
                supabase.table("screening_history")
                .select("id, job_config_id, job_title, threshold, shortlisted_count, created_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )

        records = []
        for h in history_res.data:
            try:
                try:
                    candidates_res = (
                        supabase.table("shortlisted_candidates")
                        .select("candidate_name, candidate_email, candidate_phone, final_score, linkedin, github, portfolio")
                        .eq("history_id", h["id"])
                        .execute()
                    )
                except Exception:
                    candidates_res = (
                        supabase.table("shortlisted_candidates")
                        .select("candidate_name, candidate_email, candidate_phone, final_score")
                        .eq("history_id", h["id"])
                        .execute()
                    )
                candidates = candidates_res.data
            except Exception:
                candidates = []

            job_snapshot = h.get("job_snapshot") or {}
            if not job_snapshot and h.get("job_config_id"):
                jc = get_job_config(h.get("job_config_id"), user_id=user_id) or {}
                job_snapshot = {
                    "job_title": jc.get("job_title", h.get("job_title", "Untitled Job")),
                    "qualification": jc.get("required_qualification", ""),
                    "year_of_passing": jc.get("required_year_of_passing", []),
                    "required_experience": jc.get("required_experience", 0),
                    "must_have_skills": jc.get("must_have_skills", []),
                    "good_to_have_skills": jc.get("good_to_have_skills", []),
                    "job_description": jc.get("job_description", ""),
                }
            must_have = job_snapshot.get("must_have_skills", [])
            good_to_have = job_snapshot.get("good_to_have_skills", [])
            if isinstance(must_have, str):
                must_have = [s.strip() for s in must_have.split(",") if s.strip()]
            if isinstance(good_to_have, str):
                good_to_have = [s.strip() for s in good_to_have.split(",") if s.strip()]

            timestamp_str = h["created_at"]
            try:
                from datetime import timezone, timedelta
                dt_utc = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                dt_local = dt_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
                timestamp_str = dt_local.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

            records.append({
                "id": h["id"],
                "job_config_id": h.get("job_config_id"),
                "job_title": h.get("job_title") or job_snapshot.get("job_title", "Untitled Job"),
                "qualification": job_snapshot.get("qualification", ""),
                "year_of_passing": job_snapshot.get("year_of_passing", []),
                "required_experience": job_snapshot.get("required_experience", 0),
                "must_have_skills": must_have,
                "good_to_have_skills": good_to_have,
                "job_description": job_snapshot.get("job_description", ""),
                "threshold": h["threshold"],
                "shortlisted_count": h["shortlisted_count"],
                "timestamp": timestamp_str,
                "candidates": candidates,
                "full_results": h.get("full_results") or []
            })
        return records
    except Exception as e:
        print(f"Error loading history: {e}")
        return []

def get_job_config(job_config_id: str, user_id=None):
    if supabase is None:
        return None
    try:
        query = supabase.table("job_configs").select("*").eq("id", job_config_id)
        if user_id:
            query = query.eq("user_id", user_id)
        res = query.single().execute()
        return res.data
    except Exception:
        return None

def delete_history_record(history_id: str, user_id=None):
    if user_id is None or user_id == "guest" or supabase is None:
        return

    try:
        supabase.table("screening_history") \
            .delete() \
            .eq("id", history_id) \
            .eq("user_id", user_id) \
            .execute()
    except Exception as e:
        print(f"Error deleting record: {e}")
        pass

def clear_all_history(user_id=None):
    if user_id is None or user_id == "guest" or supabase is None:
        return

    try:
        supabase.table("screening_history") \
            .delete() \
            .eq("user_id", user_id) \
            .execute()
    except Exception as e:
        print(f"Error clearing history: {e}")