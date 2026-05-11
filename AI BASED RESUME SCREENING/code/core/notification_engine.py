"""
Notification Engine Module

Sends candidate email notifications for shortlisted and rejected outcomes.
Uses SMTP settings from environment variables.
"""

import os
import smtplib
from email.message import EmailMessage
from typing import Dict, Any, List

from core.communication_engine import generate_email_draft


def _bool_env(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _smtp_config() -> Dict[str, Any]:
    return {
        "host": os.environ.get("SMTP_HOST", ""),
        "port": int(os.environ.get("SMTP_PORT", "587") or 587),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_email": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
        "use_tls": _bool_env("SMTP_USE_TLS", True),
    }


def _fallback_email(candidate: Dict[str, Any], job_data: Dict[str, Any], email_type: str) -> str:
    name = candidate.get("resume_name", "Candidate")
    job_title = job_data.get("job_title", "the role")
    if email_type == "next_steps":
        return (
            f"Hi {name},\n\n"
            f"Thank you for your interest in the {job_title} position. "
            "Based on your profile, we would like to move forward with the next steps in the hiring process.\n\n"
            "Please reply with your availability for an interview this week.\n\n"
            "Best regards,\nThe Hiring Team"
        )

    return (
        f"Hi {name},\n\n"
        f"Thank you for your interest in the {job_title} position and for taking the time to apply. "
        "After careful review, we are moving ahead with candidates whose profiles more closely match this role's immediate requirements.\n\n"
        "We appreciate your effort and wish you success in your job search.\n\n"
        "Best regards,\nThe Hiring Team"
    )


def send_candidate_notifications(candidates: List[Dict[str, Any]],
                                 job_data: Dict[str, Any],
                                 threshold: float) -> Dict[str, Any]:
    cfg = _smtp_config()

    if not (cfg["host"] and cfg["from_email"]):
        return {
            "sent": 0,
            "failed": 0,
            "skipped": len(candidates),
            "details": [],
            "error": "SMTP is not configured. Set SMTP_HOST, SMTP_USER/SMTP_FROM, and SMTP_PASSWORD.",
        }

    details = []
    sent = 0
    failed = 0
    skipped = 0

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
            if cfg["use_tls"]:
                server.starttls()
            if cfg["user"] and cfg["password"]:
                server.login(cfg["user"], cfg["password"])

            for candidate in candidates:
                recipient = candidate.get("email")
                name = candidate.get("resume_name") or candidate.get("resume_filename") or "Candidate"
                score = float(candidate.get("scores", {}).get("final_score", 0) or 0)
                email_type = "next_steps" if score >= float(threshold) else "rejection"

                if not recipient:
                    skipped += 1
                    details.append({
                        "candidate": name,
                        "status": "skipped",
                        "reason": "No email extracted",
                    })
                    continue

                subject = (
                    f"Next Steps - {job_data.get('job_title', 'Application')}"
                    if email_type == "next_steps"
                    else f"Update on Your Application - {job_data.get('job_title', 'Application')}"
                )

                draft = generate_email_draft(candidate, job_data, email_type)
                if (not draft) or draft.lower().startswith("error generating draft"):
                    draft = _fallback_email(candidate, job_data, email_type)

                msg = EmailMessage()
                msg["From"] = cfg["from_email"]
                msg["To"] = recipient
                msg["Subject"] = subject
                msg.set_content(draft)

                try:
                    server.send_message(msg)
                    sent += 1
                    details.append({
                        "candidate": name,
                        "email": recipient,
                        "status": "sent",
                        "type": email_type,
                    })
                except Exception as exc:
                    failed += 1
                    details.append({
                        "candidate": name,
                        "email": recipient,
                        "status": "failed",
                        "type": email_type,
                        "reason": str(exc),
                    })
    except Exception as exc:
        return {
            "sent": 0,
            "failed": 0,
            "skipped": len(candidates),
            "details": details,
            "error": f"SMTP connection failed: {exc}",
        }

    return {
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "details": details,
    }
