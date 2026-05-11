import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { processResumes, getResults } from '../api/client';
import JSZip from 'jszip';
import './Processing.css';

const getMimeType = (ext) => {
  const mimeTypes = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.txt': 'text/plain',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
  };
  return mimeTypes[ext] || 'application/octet-stream';
};

export default function Processing() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [dragover, setDragover] = useState(false);
  const [extractingZip, setExtractingZip] = useState(false);
  const [jobData, setJobData] = useState(null);
  const [jobLoading, setJobLoading] = useState(true);
  const fileRef = useRef(null);

  useEffect(() => {
    const loadJobData = async () => {
      try {
        const res = await getResults();
        setJobData(res.data?.job_data || null);
      } catch {
        setJobData(null);
      } finally {
        setJobLoading(false);
      }
    };
    loadJobData();
  }, [user.id]);

  const handleFiles = async (newFiles) => {
    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'image/png', 'image/jpeg', 'application/zip', 'application/x-zip-compressed'];
    let filesToAdd = [];

    for (const file of Array.from(newFiles)) {
      // Check if it's a ZIP file
      if (file.type === 'application/zip' || file.type === 'application/x-zip-compressed' || file.name.endsWith('.zip')) {
        setExtractingZip(true);
        try {
          const zip = new JSZip();
          const extractedZip = await zip.loadAsync(file);
          
          const validExtensions = ['.pdf', '.docx', '.doc', '.txt', '.png', '.jpg', '.jpeg'];
          
          for (const [filename, fileData] of Object.entries(extractedZip.files)) {
            if (!fileData.dir) {
              const ext = filename.substring(filename.lastIndexOf('.')).toLowerCase();
              if (validExtensions.includes(ext)) {
                const content = await fileData.async('arraybuffer');
                const mimeType = getMimeType(ext);
                const blob = new Blob([content], { type: mimeType });
                blob.name = filename.split('/').pop();
                filesToAdd.push(blob);
              }
            }
          }
        } catch (err) {
          setError(`Failed to extract ZIP file "${file.name}": ${err.message}`);
          setExtractingZip(false);
          continue;
        }
        setExtractingZip(false);
      } else if (validTypes.some(t => file.type.startsWith(t.split('/')[0]) || file.type === t)) {
        filesToAdd.push(file);
      }
    }

    if (filesToAdd.length > 0) {
      setFiles(prev => [...prev, ...filesToAdd]);
      setError('');
    } else if (Array.from(newFiles).length > 0) {
      setError('No valid resume files found in the uploaded file(s).');
    }
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragover(false);
    handleFiles(e.dataTransfer.files);
  }, []);

  const removeFile = (idx) => setFiles(prev => prev.filter((_, i) => i !== idx));

  const handleProcess = async () => {
    if (!files.length) { setError('Please upload at least one resume.'); return; }
    if (!jobData) { setError('No job configuration found. Please configure first.'); return; }

    setProcessing(true); setError(''); setResult(null);

    const formData = new FormData();
    formData.append('job_data', JSON.stringify(jobData));
    files.forEach(f => formData.append('resumes', f));

    try {
      const res = await processResumes(formData);
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Processing failed.');
    } finally { setProcessing(false); }
  };

  if (jobLoading) {
    return <div className="page"><div className="spinner"></div></div>;
  }

  if (!jobData) {
    return (
      <div className="page">
        <div className="alert alert-warning">Please complete job configuration first.</div>
        <button className="btn btn-primary" onClick={() => navigate('/job-config')}>📄 Go to Job Configuration</button>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>⚙️ Resume Processing</h1>
      </div>

      <div className="processing-job-info">
        <div className="job-info-item">
          <span className="job-info-label">Job Title</span>
          <span className="job-info-value">{jobData.job_title}</span>
        </div>
        <div className="job-info-divider"></div>
        <div className="job-info-item">
          <span className="job-info-label">Required Experience</span>
          <span className="job-info-value">{jobData.required_experience || 0}+ years</span>
        </div>
        {jobData.must_have_skills?.length > 0 && (
          <>
            <div className="job-info-divider"></div>
            <div className="job-info-item">
              <span className="job-info-label">Required Skills</span>
              <span className="job-info-value skills-count">{jobData.must_have_skills.length} skills</span>
            </div>
          </>
        )}
      </div>

      {error && <div className="alert alert-error"><span>❌</span> {error}</div>}

      <div
        className={`file-upload-zone ${dragover ? 'dragover' : ''}`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
        onDragLeave={() => setDragover(false)}
        onDrop={handleDrop}
      >
        <div className="upload-icon">📁</div>
        <p className="upload-title">Drag & drop resumes or ZIP files here or click to browse</p>
        <small className="upload-subtitle">PDF, DOCX, TXT, PNG, JPG supported | ZIP files will be extracted automatically</small>
        {extractingZip && <small className="upload-extracting">⏳ Extracting ZIP file...</small>}
        <input 
          ref={fileRef} 
          type="file" 
          multiple 
          accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.zip" 
          onChange={e => handleFiles(e.target.files)} 
          hidden 
        />
      </div>

      {files.length > 0 && (
        <div className="file-list-container">
          <div className="file-list-header">
            <h4>📋 Files Selected ({files.length})</h4>
            <span className="file-count-badge">{files.length}</span>
          </div>
          <div className="file-list">
            {files.map((f, i) => (
              <div key={i} className="file-item" style={{animationDelay: `${i * 50}ms`}}>
                <div className="file-item-info">
                  <span className="file-icon">📄</span>
                  <div className="file-details">
                    <span className="file-name">{f.name}</span>
                    <span className="file-size">{(f.size / 1024).toFixed(1)} KB</span>
                  </div>
                </div>
                <button 
                  className="btn-remove" 
                  onClick={() => removeFile(i)}
                  title="Remove file"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="processing-actions">
        <button 
          className="btn btn-primary btn-full btn-process" 
          onClick={handleProcess} 
          disabled={processing || !files.length}
          title={!files.length ? 'Please upload at least one resume' : 'Start processing resumes'}
        >
          {processing ? (
            <>
              <span className="spinner-mini"></span> Processing {files.length} resume(s)...
            </>
          ) : (
            <>🚀 Process Resumes</>
          )}
        </button>
      </div>

      {processing && (
        <div className="processing-state">
          <div className="processing-spinner-wrapper">
            <div className="processing-spinner"></div>
            <div className="spinner-text">Processing in parallel...</div>
          </div>
          <div className="processing-details">
            <div className="detail-item">
              <span className="detail-label">Files:</span>
              <span className="detail-value">{files.length}</span>
            </div>
          </div>
        </div>
      )}

      {result && (
        <div className="result-summary">
          <div className="result-header">
            <h3>✅ Processing Complete</h3>
            <div className="result-stats">
              <div className="stat">
                <span className="stat-value total">{result.total}</span>
                <span className="stat-label">Total</span>
              </div>
              <div className="stat">
                <span className="stat-value passed">{result.passed}</span>
                <span className="stat-label">Passed</span>
              </div>
              {result.rejected?.length > 0 && (
                <div className="stat">
                  <span className="stat-value rejected">{result.rejected.length}</span>
                  <span className="stat-label">Rejected</span>
                </div>
              )}
              {result.errors?.length > 0 && (
                <div className="stat">
                  <span className="stat-value errors">{result.errors.length}</span>
                  <span className="stat-label">Errors</span>
                </div>
              )}
            </div>
          </div>

          <div className="alert alert-success">
            <span>✅</span> Successfully processed records
          </div>

          {result.history?.saved ? (
            <div className="alert alert-success">
              <span>🗂️</span> Saved to history now (History ID: {result.history.history_id})
            </div>
          ) : (
            <div className="alert alert-warning">
              <span>⚠️</span> Processed, but history save failed: {result.history?.reason || 'unknown reason'}
            </div>
          )}

          {result.duplicates?.length > 0 && (
            <div className="alert alert-warning">
              <span>⚠️</span> Skipped {result.duplicates.length} duplicate(s): {result.duplicates.join(', ')}
            </div>
          )}

          {result.rejected?.map((r, i) => (
            <div key={i} className="alert alert-error">
              <span>🚫</span> <strong>{r.name}</strong> — {r.reason}
            </div>
          ))}

          {result.errors?.length > 0 && (
            <div className="errors-section">
              {result.errors.map((err, i) => (
                <div key={i} className="alert alert-error">
                  <span>⚠️</span> <strong>{typeof err === 'string' ? 'Error' : err.name || 'Unknown file'}</strong> — {typeof err === 'string' ? err : err.reason || err.error || 'Processing failed'}
                </div>
              ))}
            </div>
          )}

          <button 
            className="btn btn-primary btn-full btn-view-results" 
            onClick={() => navigate('/candidates')}
          >
            📊 View Shortlisted Candidates
          </button>
        </div>
      )}
    </div>
  );
}
