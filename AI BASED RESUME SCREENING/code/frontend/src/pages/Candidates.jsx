import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { getXAI, getEmailDraft, exportCSV, sendNotifications, getResults } from '../api/client';
import './Candidates.css';

function buildLocalAnalysis(jobData, candidate, threshold) {
  const scores = candidate?.scores || {};
  const finalScore = Number(scores.final_score || 0);
  const semantic = Number(scores.semantic_score || 0);
  const skill = Number(scores.skill_score || 0);
  const exp = Number(scores.experience_score || 0);
  const matched = Array.isArray(scores.matched_skills) ? scores.matched_skills : [];
  const missing = Array.isArray(scores.missing_skills) ? scores.missing_skills : [];
  const reqExp = Number(jobData?.required_experience || 0);
  const candExp = Number(candidate?.experience || 0);
  const mustHave = Array.isArray(jobData?.must_have_skills) ? jobData.must_have_skills : [];
  const mustLower = new Set(mustHave.map(s => String(s).toLowerCase()));
  const missingMust = missing.filter(s => mustLower.has(String(s).toLowerCase()));
  const matchedMust = matched.filter(s => mustLower.has(String(s).toLowerCase()));

  const verdict = finalScore >= threshold
    ? { label: 'Shortlist Recommended', color: 'green', icon: '✅' }
    : { label: 'Below Threshold', color: 'amber', icon: '⚠️' };

  const reasons = [];
  if (matchedMust.length > 0) reasons.push(`matched ${matchedMust.length} must-have skill${matchedMust.length > 1 ? 's' : ''}`);
  if (missingMust.length > 0) reasons.push(`missing ${missingMust.length} must-have skill${missingMust.length > 1 ? 's' : ''}`);
  if (reqExp > 0) reasons.push(`experience ${candExp.toFixed(1)}y vs required ${reqExp.toFixed(1)}y`);
  reasons.push(`domain relevance ${(semantic * 100).toFixed(0)}%`);

  const verdictReason = `Score ${(finalScore * 100).toFixed(1)}%: ${reasons.join(', ')}.`;

  const strengths = [];
  if (semantic >= 0.7) strengths.push({ title: 'Strong Domain Alignment', detail: `Resume shows ${(semantic * 100).toFixed(0)}% semantic relevance to the job description.` });
  if (skill >= 0.7) strengths.push({ title: 'Good Skill Match', detail: `Candidate matches ${matched.length} required skill${matched.length !== 1 ? 's' : ''}.` });
  if (reqExp > 0 && candExp >= reqExp) strengths.push({ title: 'Meets Experience Requirement', detail: `${candExp.toFixed(1)} years meets/exceeds ${reqExp.toFixed(1)} years.` });

  const risks = [];
  if (missingMust.length > 0) risks.push({ title: 'Must-Have Skill Gap', detail: `Missing: ${missingMust.slice(0, 4).join(', ')}.`, severity: missingMust.length >= 2 ? 'high' : 'medium' });
  if (reqExp > 0 && candExp < reqExp) risks.push({ title: 'Experience Gap', detail: `Candidate has ${candExp.toFixed(1)} years vs required ${reqExp.toFixed(1)} years.`, severity: (reqExp - candExp) >= 2 ? 'high' : 'medium' });

  return {
    _fallback: true,
    candidate_name: candidate?.resume_name || candidate?.resume_filename || 'Candidate',
    final_score: finalScore,
    verdict,
    verdict_reason: verdictReason,
    score_factors: [
      { name: 'Domain Relevance', value: semantic, label: semantic >= 0.85 ? 'strong' : semantic >= 0.65 ? 'good' : semantic >= 0.45 ? 'moderate' : 'weak', icon: '🎯', contribution: 0 },
      { name: 'Skill Match', value: skill, label: skill >= 0.85 ? 'strong' : skill >= 0.65 ? 'good' : skill >= 0.45 ? 'moderate' : 'weak', icon: '🛠️', contribution: 0 },
      { name: 'Experience Fit', value: exp, label: exp >= 0.85 ? 'strong' : exp >= 0.65 ? 'good' : exp >= 0.45 ? 'moderate' : 'weak', icon: '📅', contribution: 0 },
    ],
    strengths,
    risks,
    skill_analysis: {
      matched,
      matched_must: matchedMust,
      matched_good: matched.filter(s => !mustLower.has(String(s).toLowerCase())),
      missing,
      missing_must: missingMust,
      missing_good: missing.filter(s => !mustLower.has(String(s).toLowerCase())),
      coverage_pct: mustHave.length > 0 ? Math.round((matched.length / mustHave.length) * 100) : Math.round(skill * 100),
      total_required: mustHave.length,
    },
    experience_analysis: {
      candidate_years: candExp,
      required_years: reqExp,
      raw_score: exp,
      contextual_score: exp,
      verdict: reqExp <= 0 ? 'Not required' : candExp >= reqExp ? 'Meets requirement' : 'Below requirement',
    },
    evidence_snippets: [],
    penalty_info: {
      total: Number(scores?.score_breakdown?.penalty_applied || 0),
      must_have: Number(scores?.score_breakdown?.must_have_penalty || 0),
      experience_gap: Number(scores?.score_breakdown?.experience_gap_penalty || 0),
      semantic: Number(scores?.score_breakdown?.semantic_penalty || 0),
      alignment_factor: Number(scores?.score_breakdown?.irrelevancy_multiplier || 1),
    },
    qualifications: [],
    recommendation: finalScore >= threshold
      ? 'Candidate is suitable for next-stage interview based on current score profile.'
      : 'Candidate is currently below threshold; consider only if hiring pool is limited or role is flexible.',
  };
}

/* ── Rich Analysis Panel ── */
function AnalysisPanel({ analysis }) {
  if (!analysis) return (
    <div className="analysis-loading">
      <div className="analysis-loading-spinner"></div>
      <span>Generating personalized analysis…</span>
    </div>
  );

  const { verdict, strengths, risks,
      skill_analysis, experience_analysis, recommendation, executive_brief } = analysis;

  const strengthsPreview = Array.isArray(strengths) ? strengths.slice(0, 2) : [];
  const risksPreview = Array.isArray(risks) ? risks.slice(0, 1) : [];
  const matchedMustCount = skill_analysis?.matched_must?.length || 0;
  const missingMustCount = skill_analysis?.missing_must?.length || 0;
  const candidateYears = Number(experience_analysis?.candidate_years || 0);
  const requiredYears = Number(experience_analysis?.required_years || 0);
  const experienceGapYears = requiredYears > 0 ? Math.max(0, requiredYears - candidateYears) : 0;
  const topStrength = strengthsPreview[0]?.title;
  const topRisk = risksPreview[0]?.title;
  const quickSummary = executive_brief?.decision_line || [
    topStrength ? `Strength: ${topStrength}` : null,
    topRisk ? `Watchout: ${topRisk}` : null,
    !topStrength && !topRisk ? 'Candidate aligns reasonably with the current requirements.' : null,
  ].filter(Boolean).join(' | ');

  const conciseInsights = [
    strengthsPreview[0] ? strengthsPreview[0].detail : null,
    risksPreview[0] ? risksPreview[0].detail : null,
  ].filter(Boolean);

  const recruiterAction = executive_brief?.next_step || (missingMustCount > 0
    ? `Validate missing must-have skills (${missingMustCount}) in screening call before moving forward.`
    : experienceGapYears >= 1
      ? `Assess hands-on depth to confirm candidate can handle responsibilities despite ${experienceGapYears.toFixed(1)} year experience gap.`
      : `Proceed to the next round with role-specific technical questions.`);

  const interviewFocus = Array.isArray(executive_brief?.interview_focus)
    ? executive_brief.interview_focus.slice(0, 2)
    : [];

  const verdictClass = `verdict-badge verdict-${verdict?.color || 'blue'}`;

  return (
    <div className="analysis-panel">
      {/* Verdict */}
      <div className="analysis-verdict-row">
        <span className={verdictClass}>{verdict?.icon} {verdict?.label}</span>
        <span className="analysis-final-score">{(analysis.final_score * 100).toFixed(1)}%</span>
      </div>

      <div className="analysis-quick-summary">
        <div className="analysis-quick-title">Quick Summary</div>
        <p className="analysis-quick-text">{quickSummary}</p>
      </div>

      <div className="analysis-section">
        <h5 className="analysis-section-title">🧭 Recruiter Snapshot</h5>
        <div className="recruiter-snapshot-grid">
          <div className="snapshot-item">
            <div className="snapshot-label">Decision</div>
            <div className="snapshot-value">{verdict?.label || 'Review Needed'}</div>
          </div>
          <div className="snapshot-item">
            <div className="snapshot-label">Confidence</div>
            <div className="snapshot-value">{executive_brief?.confidence || 'Medium'}</div>
          </div>
          <div className="snapshot-item">
            <div className="snapshot-label">Must-Have Coverage</div>
            <div className="snapshot-value">
              {missingMustCount > 0
                ? `${matchedMustCount} matched, ${missingMustCount} missing`
                : `${matchedMustCount} matched, no critical gaps`}
            </div>
          </div>
          <div className="snapshot-item snapshot-item-full">
            <div className="snapshot-label">Experience Fit</div>
            <div className="snapshot-value">
              {requiredYears <= 0
                ? 'Open requirement'
                : experienceGapYears > 0
                  ? `${experienceGapYears.toFixed(1)} year gap`
                  : 'Meets required experience'}
            </div>
          </div>
          <div className="snapshot-item snapshot-item-full">
            <div className="snapshot-label">Recommended Next Step</div>
            <div className="snapshot-value">{recruiterAction}</div>
          </div>
        </div>
      </div>

      {interviewFocus.length > 0 && (
        <div className="analysis-section">
          <h5 className="analysis-section-title">🧪 Interview Focus</h5>
          <ul className="concise-insights-list">
            {interviewFocus.map((item, idx) => (
              <li key={idx} className="concise-insight-item">{item}</li>
            ))}
          </ul>
        </div>
      )}

      {conciseInsights.length > 0 && (
        <div className="analysis-section">
          <h5 className="analysis-section-title">🔍 Key Insights</h5>
          <ul className="concise-insights-list">
            {conciseInsights.map((insight, idx) => (
              <li key={idx} className="concise-insight-item">{insight}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Recommendation */}
      <div className="analysis-recommendation">
        <span className="rec-icon">💡</span>
        <span>{recommendation}</span>
      </div>
    </div>
  );
}


export default function Candidates() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [processingData, setProcessingData] = useState(null);
  const [jobData, setJobData] = useState(null);
  const [loadingData, setLoadingData] = useState(true);

  const [threshold, setThreshold] = useState(0.65);
  const [comparisonIds, setComparisonIds] = useState(new Set());
  const [showComparison, setShowComparison] = useState(false);
  const [expandedCard, setExpandedCard] = useState(0);
  const [analysisCache, setAnalysisCache] = useState({});
  const [draftTarget, setDraftTarget] = useState(null);
  const [draftContent, setDraftContent] = useState('');
  const [draftLoading, setDraftLoading] = useState(false);
  const [notifyLoading, setNotifyLoading] = useState(false);
  const [notifyMessage, setNotifyMessage] = useState('');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const loadSessionResults = async () => {
      try {
        const res = await getResults();
        setJobData(res.data?.job_data || null);
        setProcessingData({ results: res.data?.results || [] });
      } catch {
        setJobData(null);
        setProcessingData(null);
      } finally {
        setLoadingData(false);
      }
    };

    loadSessionResults();
  }, [user.id]);

  const results = useMemo(() => processingData?.results || [], [processingData]);

  const shortlisted = useMemo(() =>
    results.filter(r => r.scores?.final_score >= threshold)
      .sort((a, b) => b.scores.final_score - a.scores.final_score),
    [results, threshold]
  );

  const rejected = useMemo(() =>
    results.filter(r => r.scores?.final_score < threshold),
    [results, threshold]
  );

  const avgScore = shortlisted.length
    ? shortlisted.reduce((s, c) => s + c.scores.final_score, 0) / shortlisted.length
    : 0;

  const candidateKey = (c) => {
    const filename = c.resume_filename || '';
    const name = c.resume_name || '';
    const email = c.email || '';
    const score = Number(c.scores?.final_score || 0).toFixed(4);
    const exp = Number(c.experience || 0).toFixed(2);
    return `${filename}|${name}|${email}|${score}|${exp}`;
  };

  const resultSignature = useMemo(() => (
    results
      .map(c => `${c.resume_filename || ''}:${Number(c.scores?.final_score || 0).toFixed(4)}:${Number(c.experience || 0).toFixed(2)}`)
      .join('|')
  ), [results]);

  useEffect(() => {
    setAnalysisCache({});
  }, [resultSignature, jobData?.job_title]);

  // Load analysis for expanded candidate
  useEffect(() => {
    if (!jobData || expandedCard < 0 || expandedCard >= shortlisted.length) return;
    const c = shortlisted[expandedCard];
    const key = candidateKey(c);
    if (analysisCache[key]) return;

    getXAI(jobData, c)
      .then(res => {
        if (res.data?.analysis) {
          setAnalysisCache(prev => ({ ...prev, [key]: res.data.analysis }));
        } else if (res.data?.explanation) {
          // Backward-compatible fallback for older backend payloads
          const local = buildLocalAnalysis(jobData, c, threshold);
          local.text_summary = typeof res.data.explanation === 'string' ? res.data.explanation : local.verdict_reason;
          setAnalysisCache(prev => ({ ...prev, [key]: local }));
        } else {
          setAnalysisCache(prev => ({ ...prev, [key]: buildLocalAnalysis(jobData, c, threshold) }));
        }
      })
      .catch(err => {
        console.error('Analysis loading error:', err.response?.data || err.message);
        setAnalysisCache(prev => ({ ...prev, [key]: buildLocalAnalysis(jobData, c, threshold) }));
      });
  }, [expandedCard, shortlisted, jobData, analysisCache, threshold]);

  const toggleComparison = (filename) => {
    setComparisonIds(prev => {
      const next = new Set(prev);
      if (next.has(filename)) { next.delete(filename); }
      else if (next.size < 3) { next.add(filename); }
      return next;
    });
  };

  const handleDraft = async (candidate, type) => {
    setDraftLoading(true);
    setDraftTarget(candidate.resume_name);
    try {
      const res = await getEmailDraft(candidate, jobData, type);
      setDraftContent(res.data.draft);
    } catch { setDraftContent('Error generating draft.'); }
    finally { setDraftLoading(false); }
  };

  const handleExport = async () => {
    setExporting(true);
    try { 
      await exportCSV(shortlisted, jobData); 
    }
    catch (e) { 
      console.error('Export error:', e);
      alert('Export failed: ' + (e.message || 'Unknown error'));
    }
    finally { setExporting(false); }
  };

  const handleSendNotifications = async () => {
    setNotifyLoading(true);
    setNotifyMessage('');
    try {
      const res = await sendNotifications(results, jobData, threshold);
      const sent = res.data?.sent || 0;
      const failed = res.data?.failed || 0;
      const skipped = res.data?.skipped || 0;
      setNotifyMessage(`Notifications sent: ${sent}, failed: ${failed}, skipped: ${skipped}.`);
    } catch (err) {
      setNotifyMessage(err?.response?.data?.error || 'Failed to send notifications.');
    } finally {
      setNotifyLoading(false);
    }
  };

  if (loadingData) {
    return <div className="page"><div className="spinner"></div></div>;
  }

  if (!processingData || !jobData || results.length === 0) {
    return (
      <div className="page">
        <div className="alert alert-warning">No active screening session found.</div>
        <button className="btn btn-primary" onClick={() => navigate('/job-config')}>Go to Job Configuration</button>
      </div>
    );
  }

  const comparisonData = shortlisted.filter(r => comparisonIds.has(r.resume_filename)).slice(0, 3);

  return (
    <div className="page">
      <div className="page-header">
        <h1>🧑‍💼 Shortlisted Candidates</h1>
      </div>

      {/* Threshold Slider */}
      <div className="threshold-section glass-card">
        <div className="flex-between">
          <label>Shortlisting Threshold</label>
          <span className="threshold-value">{(threshold * 100).toFixed(0)}%</span>
        </div>
        <input type="range" className="slider" min={0} max={1} step={0.01} value={threshold} onChange={e => setThreshold(parseFloat(e.target.value))} />
      </div>

      {/* Summary Metrics */}
      <div className="grid-4" style={{ marginTop: 20 }}>
        <div className="metric-card"><div className="metric-value">{results.length}</div><div className="metric-label">Edu Passed</div></div>
        <div className="metric-card"><div className="metric-value">{shortlisted.length}</div><div className="metric-label">Shortlisted</div></div>
        <div className="metric-card"><div className="metric-value">{rejected.length}</div><div className="metric-label">Below Threshold</div></div>
        <div className="metric-card"><div className="metric-value">{(avgScore * 100).toFixed(1)}%</div><div className="metric-label">Avg Quality</div></div>
      </div>

      {/* Comparison Bar */}
      {shortlisted.length > 0 && (
        <div className="comparison-bar" style={{ marginTop: 20 }}>
          <div className="flex-between">
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              <strong>Compare:</strong> {comparisonIds.size > 0 ? [...comparisonIds].join(', ') : 'None selected (Max 3)'}
            </span>
            <button className="btn btn-primary" onClick={() => setShowComparison(true)} disabled={comparisonIds.size < 2}>
              ⚖️ Compare Selected
            </button>
          </div>
        </div>
      )}

      {/* Comparison Panel */}
      {showComparison && comparisonData.length >= 2 && (
        <div className="comparison-panel glass-card" style={{ marginTop: 16 }}>
          <div className="flex-between" style={{ marginBottom: 16 }}>
            <h3>⚖️ Side-by-Side Comparison</h3>
            <button className="btn btn-secondary" onClick={() => setShowComparison(false)}>✖️ Close</button>
          </div>
          <div className={`grid-${comparisonData.length}`}>
            {comparisonData.map(c => (
              <div key={c.resume_filename} className="comparison-col">
                <h4>{c.resume_name}</h4>
                <div className="metric-value" style={{ fontSize: '1.3rem' }}>{(c.scores.final_score * 100).toFixed(1)}%</div>
                <div className="progress-bar" style={{ margin: '8px 0' }}><div className="progress-fill" style={{ width: `${c.scores.final_score * 100}%` }}></div></div>
                <p className="score-line">Skill: {(c.scores.skill_score * 100).toFixed(0)}%</p>
                <p className="score-line">Domain: {(c.scores.semantic_score * 100).toFixed(0)}%</p>
                <p className="score-line">Exp: {(c.scores.experience_score * 100).toFixed(0)}%</p>
                <p className="score-line"><strong>Top Skills:</strong> {c.scores.matched_skills?.slice(0, 5).join(', ')}</p>
                <p className="score-line"><strong>Experience:</strong> {c.experience} years</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="divider"></div>

      {/* Candidate Cards */}
      {shortlisted.length === 0 ? (
        <div className="alert alert-info">No candidates meet the selected threshold.</div>
      ) : (
        <>
          <h3 style={{ marginBottom: 16 }}>🏆 Top Candidates</h3>
          {shortlisted.map((candidate, idx) => {
            const rank = idx + 1;
            const score = candidate.scores.final_score;
            const filename = candidate.resume_filename;
            const name = candidate.resume_name;
            const key = candidateKey(candidate);
            const isExpanded = expandedCard === idx;
            const draftType = score >= threshold ? 'next_steps' : 'rejection';
            const analysis = analysisCache[key];

            return (
              <div key={filename} className="candidate-card expander">
                <div className="expander-header" onClick={() => setExpandedCard(isExpanded ? -1 : idx)}>
                  <div className="flex-gap">
                    <input type="checkbox" checked={comparisonIds.has(filename)} onChange={() => toggleComparison(filename)} onClick={e => e.stopPropagation()} />
                    <span>#{rank} {name} • {(score * 100).toFixed(1)}% Match</span>
                  </div>
                  <span>{isExpanded ? '▲' : '▼'}</span>
                </div>

                {isExpanded && (
                  <div className="expander-body">
                    <div className="candidate-grid-v2">
                      {/* Left: Contact + Quick Stats */}
                      <div className="candidate-info">
                        <div className="metric-value" style={{ fontSize: '1.5rem' }}>{(score * 100).toFixed(1)}%</div>
                        <div className="progress-bar" style={{ margin: '8px 0' }}><div className="progress-fill" style={{ width: `${score * 100}%` }}></div></div>
                        <p>Skills: {(candidate.scores.skill_score * 100).toFixed(0)}% | Exp: {(candidate.scores.experience_score * 100).toFixed(0)}%</p>
                        <div className="divider"></div>
                        {candidate.email && <p>📧 {candidate.email}</p>}
                        {candidate.phone && <p>📱 {candidate.phone}</p>}
                        {candidate.linkedin && <p>🔗 <a href={candidate.linkedin} target="_blank" rel="noopener noreferrer">LinkedIn</a></p>}
                        {candidate.github && <p>💻 <a href={candidate.github} target="_blank" rel="noopener noreferrer">GitHub</a></p>}
                        <div className="divider"></div>
                        <div className="candidate-actions">
                          <button className="btn btn-secondary btn-full" onClick={() => handleDraft(candidate, draftType)} disabled={draftLoading}>
                            {draftType === 'next_steps' ? 'Draft Next Steps' : 'Draft Rejection'}
                          </button>
                        </div>
                      </div>

                      {/* Right: Rich Analysis Panel */}
                      <div className="candidate-analysis">
                        <h4>Recruiter Analysis</h4>
                        <AnalysisPanel analysis={analysis} />
                      </div>
                    </div>

                    {draftTarget === name && (
                      <>
                        <div className="divider"></div>
                        <h4>Draft ({draftType.replace('_', ' ')})</h4>
                        <textarea className="textarea" value={draftContent} onChange={e => setDraftContent(e.target.value)} rows={8} />
                        <button className="btn btn-secondary" style={{ marginTop: 8 }} onClick={() => setDraftTarget(null)}>Close Draft</button>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}

      {/* Below Threshold */}
      {rejected.length > 0 && (
        <details className="rejected-section">
          <summary>🚫 Below Threshold ({rejected.length})</summary>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 12 }}>
            These candidates passed education requirements but scored below your threshold.
          </p>
          {rejected.map((c, i) => (
            <div key={i} className="rejected-item flex-between">
              <span>{c.resume_name} ({(c.scores.final_score * 100).toFixed(1)}%)</span>
              <button className="btn btn-secondary" onClick={() => handleDraft(c, 'rejection')}>Draft Rejection</button>
            </div>
          ))}
        </details>
      )}

      <div className="divider"></div>

      {/* Export */}
      <h3 style={{ marginBottom: 12 }}>📥 Export Results</h3>
      <div className="grid-2">
        <button className="btn btn-primary btn-full" onClick={handleExport} disabled={exporting || !shortlisted.length}>
          {exporting ? 'Exporting...' : '📊 Download CSV'}
        </button>
        <button className="btn btn-primary btn-full" onClick={handleSendNotifications} disabled={notifyLoading || !results.length}>
          {notifyLoading ? 'Sending...' : '📧 Send Notifications'}
        </button>
      </div>
      {notifyMessage && (
        <div className="alert alert-info" style={{ marginTop: 12 }}>{notifyMessage}</div>
      )}

      <div className="grid-2" style={{ marginTop: 12 }}>
        <button className="btn btn-secondary btn-full" onClick={() => navigate('/history')}>
          📊 Go to History Dashboard
        </button>
      </div>
    </div>
  );
}
