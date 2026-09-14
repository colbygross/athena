import React from 'react';

function OverviewTab({ overviewData, setActiveTab, fileUrl, handleFormSubmit }) {
  if (!overviewData) return null;

  return (
    <div>
      <header className="page-header">
        <h1 className="page-title text-gradient-cyan glitch-text">Overview</h1>
        <p className="page-subtitle">Athena Diagnostics: Link Established</p>
      </header>

      {/* Stat Summary Cards */}
      <div className="grid-overview">
        <div className="glass-panel stat-card finances">
          <span className="stat-label">Monthly Spending</span>
          <span className="stat-value">${overviewData.monthly_expense.toFixed(2)}</span>
          <span className="stat-trend neutral">This month</span>
        </div>
        <div className="glass-panel stat-card health">
          <span className="stat-label">Workouts (Last 7 Days)</span>
          <span className="stat-value">{overviewData.weekly_workouts}</span>
          <span className="stat-trend up">sessions</span>
        </div>
        <div className="glass-panel stat-card learning">
          <span className="stat-label">Hours Studied (7D)</span>
          <span className="stat-value">{overviewData.weekly_learning_hours} hrs</span>
          <span className="stat-trend up">focused time</span>
        </div>
        <div className="glass-panel stat-card career">
          <span className="stat-label">Active Applications</span>
          <span className="stat-value">{overviewData.active_jobs}</span>
          <span className="stat-trend neutral">leads</span>
        </div>
      </div>

      <div className="grid-2col">
        {/* Left Column: Recent Activity */}
        <div className="glass-panel">
          <div className="panel-header">
            <h3 className="panel-title">Recent Transactions</h3>
            <button className="btn-secondary" onClick={() => setActiveTab('finances')}>View All</button>
          </div>
          <div className="panel-content">
            {overviewData.recent_transactions.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>No transactions logged yet.</p>
            ) : (
              <div className="item-list">
                {overviewData.recent_transactions.map((tx) => (
                  <div key={tx.id} className="list-item">
                    <div className="item-meta">
                      <span className="item-title">{tx.merchant || "Unknown Merchant"}</span>
                      <span className="item-subtitle">{tx.date} • {tx.category}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <span className={`badge badge-${tx.type}`}>
                        {tx.type.toUpperCase()}
                      </span>
                      <span className="item-value" style={{ color: tx.type === 'expense' ? 'var(--color-danger)' : tx.type === 'transfer' ? 'var(--accent-yellow)' : 'var(--color-success)' }}>
                        ${tx.amount.toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Files Processed */}
        <div className="glass-panel">
          <div className="panel-header">
            <h3 className="panel-title">Recently Sorted Files</h3>
            <button className="btn-secondary" onClick={() => setActiveTab('inbox')}>Inbox</button>
          </div>
          <div className="panel-content">
            {overviewData.recent_files.length === 0 ? (
              <div className="inbox-empty-state">
                <span className="inbox-empty-icon">📁</span>
                <p>No documents processed yet. Drop some in your Vault's Inbox folder!</p>
              </div>
            ) : (
              <div className="item-list">
                {overviewData.recent_files.map((file) => (
                  <a key={file.id} href={fileUrl(file.new_path)} target="_blank" rel="noopener noreferrer" className="list-item" style={{ textDecoration: 'none', color: 'inherit' }}>
                    <div className="item-meta">
                      <span className="item-title">{file.original_name}</span>
                      <span className="item-subtitle">Sorted to: {file.category.toUpperCase()}</span>
                    </div>
                    <span className="file-icon">📄</span>
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Quick Habits Log */}
      <div className="glass-panel" style={{ marginTop: '1.5rem' }}>
        <div className="panel-header">
          <h3 className="panel-title">Today's Habit Checklist</h3>
          <button className="btn-secondary" onClick={() => setActiveTab('habits')}>View Streaks</button>
        </div>
        <div className="panel-content">
          <div className="habits-grid">
            {['Code 1 Hour', 'Read 10 pages', 'Workout', 'Drink 3L Water', 'Sleep 8 hours'].map(habitName => {
              const logged = overviewData.todays_habits.find(h => h.habit_name === habitName);
              const isCompleted = logged ? logged.completed === 1 : false;
              return (
                <div 
                  key={habitName} 
                  className={`glass-panel habit-card ${isCompleted ? 'completed' : ''}`}
                  onClick={() => handleFormSubmit(
                    'habits', 
                    { date: new Date().toISOString().split('T')[0], habit_name: habitName, completed: isCompleted ? 0 : 1, notes: 'Quick logged from dashboard' },
                    () => {},
                    {}
                  )}
                >
                  <div className="habit-checkbox">✔</div>
                  <span className="habit-title">{habitName}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default OverviewTab;
