# AI Resume Screening System

An AI-assisted resume screening platform with a Flask backend API and React frontend.

## Features

- Semantic resume to job matching using embeddings
- Skill, experience, qualification, and contact extraction
- Weighted candidate scoring and threshold-based shortlisting
- Explainable analysis for each candidate
- Email draft generation and notification support
- Screening history with reload and export
- Supabase-backed authentication and per-user sessions

## Tech Stack

- Backend: Flask, Flask-CORS, Python
- Frontend: React, Vite
- AI/NLP: sentence-transformers, torch, rapidfuzz
- Parsing: PyMuPDF, pdfplumber, python-docx, pytesseract
- Data/Auth: Supabase

## Prerequisites

- Python 3.10+
- Node.js 18+
- npm

## Backend Setup

1. Create and activate a virtual environment.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install Python dependencies.

```bash
pip install -r requirements.txt
```

3. Configure Supabase environment values used by supabase_client.py.

- SUPABASE_URL
- SUPABASE_ANON_KEY

## Frontend Setup

```bash
cd frontend
npm install
```

## Run the Application

Open two terminals from the project root.

1. Start backend API:

```bash
python api/server.py
```

Backend runs at http://127.0.0.1:5000.

2. Start frontend dev server:

```bash
cd frontend
npm run dev
```

Frontend runs at http://127.0.0.1:5173 and proxies /api to http://localhost:5000 via [frontend/vite.config.js](frontend/vite.config.js).

## API Quick Checks

- GET /api/health -> service health
- GET /api/status -> backend status
- POST /api/auth/login -> login
- POST /api/job-config -> save job config (auth required)
- POST /api/process -> process resumes (auth required)
- GET /api/results -> current session results (auth required)
- GET /api/history -> history list (auth required)

## Scoring

Final score uses weighted factors from [core/config.py](core/config.py):

- semantic similarity
- skill match
- experience fit
- penalties for missing requirements

Tune weights and threshold in [core/config.py](core/config.py).

## Project Structure

```text
resume_screening/
  api/
    server.py
  core/
    config.py
    embedding_engine.py
    scoring.py
    skill_extractor.py
    experience_extractor.py
    qualification_extractor.py
    contact_extractor.py
    hybrid_extractor.py
    xai_engine_v3.py
  utils/
    history_store.py
    export_utils.py
  frontend/
    src/
  data/
  requirements.txt
  supabase_client.py
```

## Developer Commands

Frontend lint:

```bash
cd frontend
npm run lint
```

Frontend production build:

```bash
cd frontend
npm run build
```

Python syntax check:

```bash
python -m compileall api core utils supabase_client.py
```

## Troubleshooting

- Frontend cannot reach backend:
  - Confirm backend is running on port 5000.
  - Confirm proxy in [frontend/vite.config.js](frontend/vite.config.js).
- 401 responses from protected APIs:
  - Ensure login succeeded and auth token is stored in localStorage session.
- Slow processing:
  - Reduce concurrent uploads or use smaller embedding models in [core/embedding_engine.py](core/embedding_engine.py).

## License

MIT
