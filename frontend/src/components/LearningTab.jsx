import React, { useState } from 'react';

function LearningTab({ learningData, handleFormSubmit, renderRelatedAreas }) {
  const getInitialFormState = () => ({
    date: new Date().toISOString().split('T')[0],
    topic: '',
    category: 'Computer Science',
    hours_spent: '',
    notes: '',
    source_link: '',
    status: 'completed'
  });

  const [learnForm, setLearnForm] = useState(getInitialFormState);

  if (!learningData) return null;

  return (
    <div>
      <header className="page-header">
        <h1 className="page-title text-gradient-purple glitch-text">Learning Tracker</h1>
        <p className="page-subtitle">CS Study: Algorithms // Systems Breach</p>
      </header>

      <div className="grid-2col">
        {/* Left Column: Learning Logs */}
        <div className="glass-panel">
          <div className="panel-header">
            <h3 className="panel-title">Learning Log History</h3>
          </div>
          <div className="panel-content">
            {learningData.logs.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>No study logs recorded yet.</p>
            ) : (
              <div className="item-list">
                {learningData.logs.map((log) => (
                  <div key={log.id} className="list-item">
                    <div className="item-meta">
                      <span className="item-title">{log.topic}</span>
                      <span className="item-subtitle">
                        {log.date} • {log.category}
                      </span>
                      {log.notes && (
                        <span className="item-subtitle learn-log-notes" style={{ fontStyle: 'italic', marginTop: '0.15rem' }}>
                          {log.notes}
                        </span>
                      )}
                      {log.source_link && (
                        <span className="learn-log-link" style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>
                          🔗 <a href={log.source_link} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-cyan)', textDecoration: 'underline' }}>
                            Reference Link / Materials
                          </a>
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.25rem' }}>
                      <span className="badge badge-income" style={{ color: log.status === 'completed' ? 'var(--color-success)' : 'var(--color-warning)' }}>
                        {(log.status || 'completed').toUpperCase()}
                      </span>
                      <span className="item-value">{log.hours_spent} hrs</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Log study session */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-panel">
            <div className="panel-header">
              <h3 className="panel-title">Log Study Session</h3>
            </div>
            <div className="panel-content">
              <form onSubmit={(e) => {
                e.preventDefault();
                handleFormSubmit(
                  'learning', 
                  {
                    date: learnForm.date,
                    topic: learnForm.topic,
                    category: learnForm.category,
                    hours_spent: parseFloat(learnForm.hours_spent),
                    notes: learnForm.notes,
                    source_link: learnForm.source_link,
                    status: learnForm.status
                  }, 
                  setLearnForm, 
                  getInitialFormState()
                );
              }}>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Date</label>
                    <input type="date" className="form-input" value={learnForm.date} onChange={e => setLearnForm({...learnForm, date: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Hours Focused</label>
                    <input type="number" step="0.5" placeholder="e.g., 2.5" className="form-input" value={learnForm.hours_spent} onChange={e => setLearnForm({...learnForm, hours_spent: e.target.value})} required />
                  </div>
                </div>
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Category</label>
                    <select className="form-select" value={learnForm.category} onChange={e => setLearnForm({...learnForm, category: e.target.value})}>
                      <option value="Computer Science">Computer Science</option>
                      <option value="Systems & Architecture">Systems & Architecture</option>
                      <option value="Web Development">Web Development</option>
                      <option value="Finance">Finance</option>
                      <option value="Languages">Languages</option>
                      <option value="General">General</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select className="form-select" value={learnForm.status} onChange={e => setLearnForm({...learnForm, status: e.target.value})}>
                      <option value="completed">Completed</option>
                      <option value="in-progress">In Progress</option>
                    </select>
                  </div>
                </div>
                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Topic / Skill</label>
                  <input type="text" placeholder="e.g., B-Trees and indexing in PostgreSQL" className="form-input" value={learnForm.topic} onChange={e => setLearnForm({...learnForm, topic: e.target.value})} required />
                </div>
                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Source URL / Book Reference</label>
                  <input type="text" placeholder="e.g., https://github.com/repository-link" className="form-input" value={learnForm.source_link} onChange={e => setLearnForm({...learnForm, source_link: e.target.value})} />
                </div>
                <div className="form-group" style={{ marginBottom: '1.5rem' }}>
                  <label className="form-label">Notes & Summary</label>
                  <textarea placeholder="Write brief notes or core concepts learned..." rows="3" className="form-textarea" value={learnForm.notes} onChange={e => setLearnForm({...learnForm, notes: e.target.value})} />
                </div>
                <button type="submit" className="btn-primary" style={{ width: '100%' }}>Log Study Session</button>
              </form>
            </div>
          </div>
          {renderRelatedAreas("Learning")}
        </div>
      </div>
    </div>
  );
}

export default LearningTab;
