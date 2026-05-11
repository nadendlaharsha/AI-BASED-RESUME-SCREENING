import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHistory, getHistoryResults, deleteHistoryRecord, clearAllHistory, setSessionData } from '../api/client';
import './History.css';

export default function History() {
  const navigate = useNavigate();
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedIdx, setExpandedIdx] = useState(-1);

  const load = async () => {
    setLoading(true);
    try {
      const res = await getHistory();
      setHistory(res.data.history || []);
    } catch {
      setError('Failed to load history.');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id) => {
    try {
      await deleteHistoryRecord(id);
      setHistory(prev => prev.filter(r => r.id !== id));
    } catch { setError('Delete failed.'); }
  };

  const handleClearAll = async () => {
    if (!confirm('Are you sure you want to clear all history?')) return;
    try {
      await clearAllHistory();
      setHistory([]);
    } catch { setError('Clear failed.'); }
  };

  const handleViewResults = async (record) => {
    try {
      const res = await getHistoryResults(record.id);
      if (res.data.results) {
        await setSessionData(res.data.job_data, res.data.results);
        navigate('/candidates');
      }
    } catch { setError('Failed to load results.'); }
  };

  const handleRescreen = (record) => {
    const jobData = {
      job_title: record.job_title || '',
      qualification: record.qualification || '',
      year_of_passing: record.year_of_passing || [],
      required_experience: record.required_experience || 0,
      must_have_skills: record.must_have_skills || [],
      good_to_have_skills: record.good_to_have_skills || [],
      job_description: record.job_description || '',
    };
    setSessionData(jobData, []).then(() => navigate('/job-config'));
  };

  if (loading) return <div className="page"><div className="spinner"></div></div>;

  return (
    <div className="page">
      <div className="page-header">
        <h1>📊 Screening History</h1>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {history.length === 0 ? (
        <>
          <div className="alert alert-info">No screening history available.</div>
          <button className="btn btn-primary" onClick={() => navigate('/job-config')}>➕ Start New Screening</button>
        </>
      ) : (
        <>
          <button className="btn btn-danger" onClick={handleClearAll} style={{ marginBottom: 16 }}>🗑️ Clear All History</button>

          {history.map((record, idx) => (
            <div key={record.id || idx} className="expander">
              <div className="expander-header" onClick={() => setExpandedIdx(expandedIdx === idx ? -1 : idx)}>
                <span>{record.job_title} — {record.timestamp}</span>
                <span>{expandedIdx === idx ? '▲' : '▼'}</span>
              </div>

              {expandedIdx === idx && (
                <div className="expander-body">
                  <div className="grid-2" style={{ marginBottom: 12 }}>
                    <div>
                      <p><strong>Threshold:</strong> {typeof record.threshold === 'number' ? (record.threshold * 100).toFixed(0) + '%' : record.threshold}</p>
                      <p><strong>Shortlisted:</strong> {record.shortlisted_count}</p>
                      {record.qualification && <p><strong>Qualification:</strong> {Array.isArray(record.qualification) ? record.qualification.join(', ') : record.qualification}</p>}
                    </div>
                    <div>
                      {record.required_experience > 0 && <p><strong>Experience:</strong> {record.required_experience} years</p>}
                      {record.year_of_passing?.length > 0 && <p><strong>Years:</strong> {record.year_of_passing.join(', ')}</p>}
                      {record.must_have_skills?.length > 0 && <p><strong>Skills:</strong> {record.must_have_skills.join(', ')}</p>}
                    </div>
                  </div>

                  {/* Candidates Table */}
                  {record.candidates?.length > 0 ? (
                    <div className="table-responsive">
                      <table className="history-table">
                        <thead>
                          <tr>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Phone</th>
                            <th>Profiles</th>
                            <th>Score</th>
                          </tr>
                        </thead>
                        <tbody>
                          {record.candidates.map((c, ci) => (
                            <tr key={ci}>
                              <td>{c.candidate_name || c.name || 'N/A'}</td>
                              <td>{c.candidate_email || c.email || ''}</td>
                              <td>{c.candidate_phone || c.phone || ''}</td>
                              <td>
                                {[c.linkedin, c.github, c.portfolio].filter(Boolean).length > 0
                                  ? [c.linkedin, c.github, c.portfolio].filter(Boolean).join(' | ')
                                  : ''}
                              </td>
                              <td>{c.final_score != null ? (parseFloat(c.final_score) * 100).toFixed(1) + '%' : ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="alert alert-info">No candidates passed the threshold.</div>
                  )}

                  <div className="flex-gap" style={{ marginTop: 16, flexWrap: 'wrap' }}>
                    {record.has_full_results && (
                      <button className="btn btn-primary" onClick={() => handleViewResults(record)}>👁️ View Complete Results</button>
                    )}
                    <button className="btn btn-secondary" onClick={() => handleRescreen(record)}>🔄 Re-screen</button>
                    <button className="btn btn-danger" onClick={() => handleDelete(record.id)}>❌ Delete</button>
                  </div>
                </div>
              )}
            </div>
          ))}

          <div className="divider"></div>
          <button className="btn btn-primary" onClick={() => navigate('/job-config')}>➕ Start New Screening</button>
        </>
      )}
    </div>
  );
}
