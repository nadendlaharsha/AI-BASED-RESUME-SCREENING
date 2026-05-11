import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import { saveJobConfig, getResults } from '../api/client';
import './JobConfig.css';

const SKILL_OPTIONS = [
  "Python","Java","JavaScript","TypeScript","C++","C#","Go","Rust","PHP","Ruby","Swift","Kotlin","R","MATLAB","Scala","HTML","CSS",
  "React","Angular","Vue.js","Node.js","Express.js","Django","Flask","FastAPI","Spring Boot","ASP.NET","Laravel","Next.js","Svelte","Bootstrap","Tailwind CSS",
  "React Native","Flutter","Android Development","iOS Development",
  "SQL","MySQL","PostgreSQL","MongoDB","Redis","Oracle","SQLite","Cassandra","DynamoDB","Firebase","Elasticsearch",
  "AWS","Azure","Google Cloud Platform","Docker","Kubernetes","CI/CD","Jenkins","Terraform","Linux","Shell Scripting",
  "Machine Learning","Deep Learning","TensorFlow","PyTorch","Scikit-learn","Pandas","NumPy","Data Analysis","Data Visualization","Power BI","Tableau","Apache Spark","NLP","Computer Vision",
  "Git","REST APIs","GraphQL","Microservices","Agile","Scrum","JIRA","Testing","Unit Testing","Selenium","Jest","Pytest","API Development","System Design","Object-Oriented Programming","Data Structures","Algorithms",
  "Communication","Leadership","Problem Solving","Team Collaboration","Project Management","Time Management","Critical Thinking","Analytical Skills"
].sort();

const QUAL_OPTIONS = ["None","BTech","MTech","MCA","MBA","BCA","Any Bachelor's","Any Master's"];

export default function JobConfig() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [jobTitle, setJobTitle] = useState('');
  const [jobDesc, setJobDesc] = useState('');
  const [qualifications, setQualifications] = useState(['None']);
  const [yearOfPassing, setYearOfPassing] = useState('');
  const [experience, setExperience] = useState(0);
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [customSkills, setCustomSkills] = useState('');
  const [goodToHave, setGoodToHave] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [skillSearch, setSkillSearch] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [touched, setTouched] = useState({});
  const dropdownRef = useRef(null);

  useEffect(() => {
    const preload = async () => {
      try {
        const res = await getResults();
        const data = res.data?.job_data || null;
        if (!data) return;

        if (data.job_title) setJobTitle(data.job_title);
        if (data.job_description) setJobDesc(data.job_description);

        let quals = data.qualification || data.required_qualification || [];
        if (typeof quals === 'string') quals = quals.split(',').map(s => s.trim()).filter(Boolean);
        if (quals.length) setQualifications(quals);

        let years = data.year_of_passing || data.required_year_of_passing || [];
        if (Array.isArray(years)) setYearOfPassing(years.join(', '));

        if (data.required_experience) setExperience(Number(data.required_experience));

        let mustHave = data.must_have_skills || [];
        if (typeof mustHave === 'string') mustHave = mustHave.split(',').map(s => s.trim()).filter(Boolean);
        const std = [], cust = [];
        mustHave.forEach(s => {
          if (SKILL_OPTIONS.includes(s)) std.push(s);
          else if (s) cust.push(s);
        });
        setSelectedSkills(std);
        if (cust.length) setCustomSkills(cust.join(', '));

        let goodHave = data.good_to_have_skills || [];
        if (typeof goodHave === 'string') goodHave = goodHave.split(',').map(s => s.trim()).filter(Boolean);
        if (goodHave.length) setGoodToHave(goodHave.join(', '));
      } catch (e) {
        console.error('Failed to preload job data', e);
      }
    };

    preload();
  }, [user.id]);

  const wordCount = jobDesc.trim() ? jobDesc.trim().split(/\s+/).length : 0;
  const customSkillsList = customSkills ? customSkills.split(',').map(s => s.trim()).filter(Boolean) : [];
  
  // Validation states
  const isJobTitleValid = jobTitle.trim().length > 0;
  const isJobDescValid = wordCount >= 30 && wordCount <= 2500;
  const isSkillsValid = selectedSkills.length + customSkillsList.length > 0;
  const allFieldsValid = isJobTitleValid && isJobDescValid && isSkillsValid;

  const toggleQual = (q) => {
    setQualifications(prev => {
      if (q === 'None') return ['None'];
      const next = prev.filter(x => x !== 'None');
      return next.includes(q) ? next.filter(x => x !== q) : [...next, q];
    });
  };

  const addSkill = (skill) => {
    if (!selectedSkills.includes(skill)) setSelectedSkills(prev => [...prev, skill]);
    setSkillSearch('');
    setShowDropdown(false);
  };

  const removeSkill = (skill) => setSelectedSkills(prev => prev.filter(s => s !== skill));

  const filteredOptions = SKILL_OPTIONS.filter(
    s => s.toLowerCase().includes(skillSearch.toLowerCase()) && !selectedSkills.includes(s)
  ).slice(0, 15);

  const handleSubmit = async () => {
    if (!jobTitle || !jobDesc) { setError('Job title and description are required.'); return; }
    if (wordCount < 30) { setError(`Job description needs at least 30 words (current: ${wordCount}).`); return; }
    if (wordCount > 2500) { setError(`Job description exceeds 2500 words (current: ${wordCount}).`); return; }

    setLoading(true); setError('');

    const mustHaveList = [...selectedSkills];
    if (customSkills) {
      customSkills.split(',').forEach(s => {
        const trimmed = s.trim();
        if (trimmed && !mustHaveList.includes(trimmed)) mustHaveList.push(trimmed);
      });
    }

    const goodList = goodToHave ? goodToHave.split(',').map(s => s.trim()).filter(Boolean) : [];
    const yearList = yearOfPassing ? yearOfPassing.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n)) : [];

    try {
      await saveJobConfig({
        job_title: jobTitle,
        job_description: jobDesc,
        qualification: qualifications,
        year_of_passing: yearList,
        required_experience: experience,
        must_have_skills: mustHaveList,
        good_to_have_skills: goodList
      });
      navigate('/processing');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to save job config.');
    } finally { setLoading(false); }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>📄 Job Configuration</h1>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      <div className="form-group">
        <label>Job Title {isJobTitleValid && <span className="field-check">✓</span>}</label>
        <input 
          className={`input ${isJobTitleValid ? 'input-valid' : touched.jobTitle && !isJobTitleValid ? 'input-invalid' : ''}`}
          value={jobTitle} 
          onChange={e => setJobTitle(e.target.value)}
          onBlur={() => setTouched({...touched, jobTitle: true})}
          placeholder="e.g. Senior Python Developer" 
        />
        {touched.jobTitle && !isJobTitleValid && <span className="field-error">Job title is required</span>}
      </div>

      <div className="form-group">
        <label>Job Description {isJobDescValid && <span className="field-check">✓</span>}</label>
        <textarea 
          className={`textarea ${isJobDescValid ? 'input-valid' : touched.jobDesc && !isJobDescValid ? 'input-invalid' : ''}`}
          value={jobDesc} 
          onChange={e => setJobDesc(e.target.value)}
          onBlur={() => setTouched({...touched, jobDesc: true})}
          placeholder="Enter the full job description..." 
          rows={6} 
        />
        <div className="field-info">
          <small className={`word-count ${wordCount < 30 || wordCount > 2500 ? 'word-count-red' : 'word-count-green'}`}>
            {wordCount < 30 ? '🔴' : wordCount > 2500 ? '⚠️' : '🟢'} 
            Word count: <strong>{wordCount}</strong> / 30–2,500
            {wordCount < 30 && ` (+${30 - wordCount} more needed)`}
            {wordCount > 2500 && ` (−${wordCount - 2500} words over)`}
          </small>
        </div>
      </div>

      <div className="divider"></div>
      <h3 className="section-heading">📋 Job Requirements</h3>

      <div className="grid-2">
        <div className="form-group">
          <label>Required Qualification(s)</label>
          <div className="qual-grid">
            {QUAL_OPTIONS.map(q => (
              <label key={q} className={`qual-chip ${qualifications.includes(q) ? 'qual-active' : ''}`} title={`Select ${q}`}>
                <input type="checkbox" checked={qualifications.includes(q)} onChange={() => toggleQual(q)} hidden />
                {q}
              </label>
            ))}
          </div>
          {!qualifications.includes('None') && (
            <div className="form-group" style={{ marginTop: 12 }}>
              <label>Allowed Years of Passing <span className="field-hint">(comma separated)</span></label>
              <input 
                className="input" 
                value={yearOfPassing} 
                onChange={e => setYearOfPassing(e.target.value)}
                onBlur={() => setTouched({...touched, yearOfPassing: true})}
                placeholder="e.g., 2022, 2023, 2024" 
              />
              <small className="field-hint">Enter graduation years when candidates are eligible</small>
            </div>
          )}
        </div>
        <div className="form-group">
          <label>Required Experience (Years)</label>
          <div className="experience-input-wrapper">
            <button 
              type="button"
              className="experience-btn experience-btn-minus"
              onClick={() => setExperience(Math.max(0, experience - 1))}
              title="Decrease experience"
            >
              −
            </button>
            <div className="experience-input-shell">
              <input 
                className="input experience-input" 
                type="number" 
                min={0}
                max={60}
                value={experience} 
                onChange={e => setExperience(Math.max(0, parseInt(e.target.value) || 0))}
                onBlur={() => setTouched({...touched, experience: true})}
              />
              {experience > 0 && <span className="experience-badge">{experience}+ yrs</span>}
            </div>
            <button 
              type="button"
              className="experience-btn experience-btn-plus"
              onClick={() => setExperience(Math.min(60, experience + 1))}
              title="Increase experience"
            >
              +
            </button>
          </div>
          <div className="experience-info">
            {experience === 0 && <small className="field-hint">Freshers welcome</small>}
            {experience > 0 && experience <= 2 && <small className="field-hint">Entry-level / Junior</small>}
            {experience > 2 && experience <= 5 && <small className="field-hint">Mid-level</small>}
            {experience > 5 && <small className="field-hint">Senior level</small>}
          </div>
        </div>
      </div>

      <div className="divider"></div>
      <h3 className="section-heading">🔧 Skills Requirements</h3>

      <div className="form-group">
        <label>Required Skills {isSkillsValid && <span className="field-check">✓</span>} <span className="field-hint">({selectedSkills.length + customSkillsList.length} selected)</span></label>
        <div className="multiselect-container" ref={dropdownRef}>
          <div className="multiselect-tags" onClick={() => setShowDropdown(true)}>
            {selectedSkills.map(s => (
              <span key={s} className="multiselect-tag">{s} <button onClick={(e) => { e.stopPropagation(); removeSkill(s); }} title="Remove">×</button></span>
            ))}
            <input
              className="multiselect-input"
              value={skillSearch}
              onChange={e => { setSkillSearch(e.target.value); setShowDropdown(true); }}
              onFocus={() => setShowDropdown(true)}
              placeholder={selectedSkills.length === 0 ? 'Search and select required skills...' : 'Add more...'}
            />
          </div>
          {showDropdown && (
            <>
              {filteredOptions.length > 0 && (
                <div className="multiselect-dropdown">
                  <div className="multiselect-header">{filteredOptions.length} available</div>
                  {filteredOptions.map(s => (
                    <div key={s} className="multiselect-option" onClick={() => addSkill(s)}>{s}</div>
                  ))}
                </div>
              )}
              {skillSearch && filteredOptions.length === 0 && (
                <div className="multiselect-dropdown multiselect-empty">
                  <div className="multiselect-header">No matches found</div>
                </div>
              )}
            </>
          )}
        </div>
        <small className="field-hint">Select from standard skills or add custom skills below</small>
      </div>

      <div className="form-group">
        <label>Complementary Skills <span className="field-hint">(comma separated, optional)</span></label>
        <input 
          className="input" 
          value={customSkills} 
          onChange={e => setCustomSkills(e.target.value)}
          onBlur={() => setTouched({...touched, customSkills: true})}
          placeholder="e.g., SAP, Salesforce, domain-specific tools..." 
        />
        {customSkillsList.length > 0 && (
          <div className="field-info">
            <small className="field-hint">{customSkillsList.length} custom skill{customSkillsList.length !== 1 ? 's' : ''} added</small>
          </div>
        )}
      </div>

      <div className="form-group">
        <label>Preferred Qualifications <span className="field-hint">(comma separated, optional)</span></label>
        <input 
          className="input" 
          value={goodToHave} 
          onChange={e => setGoodToHave(e.target.value)}
          onBlur={() => setTouched({...touched, goodToHave: true})}
          placeholder="e.g., AWS certification, team lead experience..." 
        />
      </div>

      <div className="divider"></div>

      <div className="grid-2">
        <button 
          className={`btn btn-primary btn-full ${loading ? 'btn-loading' : ''}`}
          onClick={handleSubmit} 
          disabled={loading || !allFieldsValid}
          title={!allFieldsValid ? 'Please fill all required fields properly' : 'Save and continue to resume processing'}
        >
          {loading ? (
            <>
              <span className="spinner-mini"></span> Saving...
            </>
          ) : (
            <>💾 Save & Continue</>
          )}
        </button>
        <button 
          className="btn btn-secondary btn-full"
          onClick={() => navigate('/history')}
          disabled={loading}
        >
          📊 View History
        </button>
      </div>
    </div>
  );
}
