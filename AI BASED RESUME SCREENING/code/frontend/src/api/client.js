import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
});

api.interceptors.request.use((config) => {
  try {
    const raw = localStorage.getItem('session');
    if (raw) {
      const session = JSON.parse(raw);
      const token = session?.access_token;
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
  } catch {
    // Ignore malformed local session payload.
  }
  return config;
});

// Status
export const getStatus = () => api.get('/status');

// Auth
export const login = (email, password) =>
  api.post('/auth/login', { email, password });

export const signup = (email, password) =>
  api.post('/auth/signup', { email, password });

export const guestLogin = () =>
  api.post('/auth/guest');

// Job Config
export const saveJobConfig = (data) =>
  api.post('/job-config', data);

// Processing
export const processResumes = (formData) =>
  api.post('/process', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000
  });

// Results
export const getResults = () =>
  api.get('/results');

export const setSessionData = (jobData, results = null) => {
  const payload = { job_data: jobData };
  if (results !== null) {
    payload.results = results;
  }
  return api.post('/session', payload);
};

export const getXAI = (jobData, candidate) =>
  api.post('/results/xai', { job_data: jobData, candidate });

export const getEmailDraft = (candidate, jobData, draftType) =>
  api.post('/results/email-draft', { candidate, job_data: jobData, draft_type: draftType });

export const sendNotifications = (candidates, jobData, threshold) =>
  api.post('/results/send-notifications', { candidates, job_data: jobData, threshold });

export const exportCSV = async (candidates, jobData) => {
  const res = await api.post('/results/export-csv', { candidates, job_data: jobData }, {
    responseType: 'blob'
  });
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const link = document.createElement('a');
  link.href = url;
  const filenameRaw = res.headers['content-disposition']?.split('filename=')[1] || 'candidates.csv';
  const filename = filenameRaw.replace(/["']/g, '');
  link.setAttribute('download', filename);
  document.body.appendChild(link);
  link.click();
  link.remove();
};

// History
export const getHistory = () =>
  api.get('/history');

export const getHistoryResults = (historyId) =>
  api.get(`/history/${historyId}/results`);

export const deleteHistoryRecord = (historyId) =>
  api.delete(`/history/${historyId}`);

export const clearAllHistory = () =>
  api.delete('/history/clear');

export default api;
