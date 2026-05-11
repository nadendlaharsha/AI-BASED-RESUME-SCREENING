import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import './Home.css';

export default function Home() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const handleGetStarted = () => {
    navigate(user ? '/job-config' : '/login');
  };

  return (
    <div className="home-page">
      <div className="hero-section">
        <div className="hero-glow"></div>
        <h1 className="hero-title">🎯 AI Resume Screening System</h1>
        <p className="hero-subtitle">Llama-3 Powered Candidate Evaluation with Explainable AI</p>
        <p className="hero-desc">
          Screen resumes faster and smarter with AI-powered semantic matching,
          automated skill extraction, and clear explanations for every decision.
        </p>

        <div className="features-grid">
          <div className="feature-card glass-card">
            <h3>✨ What It Does</h3>
            <ul>
              <li>🧠 <strong>Semantic Matching</strong> — Deep understanding of resumes</li>
              <li>🔍 <strong>Skill Extraction</strong> — Automatic skill identification</li>
              <li>📊 <strong>Smart Scoring</strong> — Multi-factor evaluation</li>
            </ul>
          </div>
          <div className="feature-card glass-card">
            <h3>🚀 Why Use It</h3>
            <ul>
              <li>⚡ <strong>Fast</strong> — Process resumes in seconds</li>
              <li>📈 <strong>Accurate</strong> — AI-powered analysis</li>
              <li>📥 <strong>Export Ready</strong> — CSV, JSON, reports</li>
            </ul>
          </div>
        </div>

        <div className="divider"></div>

        <h2 className="section-title">How It Works</h2>
        <div className="steps-grid">
          <div className="step-card">
            <div className="step-number">1</div>
            <h4>Define Job</h4>
            <p>Enter requirements and skills</p>
          </div>
          <div className="step-card">
            <div className="step-number">2</div>
            <h4>Upload</h4>
            <p>Add PDF resumes</p>
          </div>
          <div className="step-card">
            <div className="step-number">3</div>
            <h4>AI Process</h4>
            <p>Get instant analysis</p>
          </div>
          <div className="step-card">
            <div className="step-number">4</div>
            <h4>Review</h4>
            <p>See ranked results</p>
          </div>
        </div>

        <div className="hero-cta">
          <button className="btn btn-primary btn-lg" onClick={handleGetStarted}>
            🚀 Get Started
          </button>
        </div>

        <p className="hero-footer">Fast • Accurate • Easy to Use</p>
      </div>
    </div>
  );
}
