import React, { useState } from 'react';
import { HABITS } from '../constants';

function HabitsTab({ habitsData, handleFormSubmit, renderRelatedAreas }) {
  const getInitialFormState = () => ({
    date: new Date().toISOString().split('T')[0],
    habit_name: 'Code 1 Hour',
    completed: 1,
    notes: ''
  });

  const [habitForm, setHabitForm] = useState(getInitialFormState);

  if (!habitsData) return null;

  return (
    <div>
      <header className="page-header page-header--compact">
        <h1 className="page-title">Habits</h1>
        <div className="page-header-meta">
          <p className="page-subtitle">Daily Routines: Repetition Sequence</p>
        </div>
      </header>

      <div className="grid-2col">
        {/* Left Column: Habits List & Streaks */}
        <div className="glass-panel">
          <div className="panel-header">
            <h3 className="panel-title">Habit History (Last 14 Days)</h3>
          </div>
          <div className="panel-content">
            {habitsData.logs.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>No habits logged in the last 2 weeks.</p>
            ) : (
              <div className="item-list">
                {habitsData.logs.map((log, idx) => (
                  <div key={idx} className="list-item">
                    <div className="item-meta">
                      <span className="item-title">{log.habit_name}</span>
                      <span className="item-subtitle">{log.date}{log.notes ? <span className="habit-log-notes"> • {log.notes}</span> : ''}</span>
                    </div>
                    <span className={`badge badge-${log.completed === 1 ? 'income' : 'expense'}`}>
                      {log.completed === 1 ? 'COMPLETED' : 'MISSED'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Custom log form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-panel">
            <div className="panel-header">
              <h3 className="panel-title">Log Daily Habit Entry</h3>
            </div>
            <div className="panel-content">
              <form onSubmit={(e) => {
                e.preventDefault();
                handleFormSubmit(
                  'habits', 
                  {
                    ...habitForm,
                    completed: parseInt(habitForm.completed)
                  }, 
                  setHabitForm, 
                  getInitialFormState()
                );
              }}>
                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Date</label>
                  <input type="date" className="form-input" value={habitForm.date} onChange={e => setHabitForm({...habitForm, date: e.target.value})} required />
                </div>
                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Habit Name</label>
                  <select className="form-select" value={habitForm.habit_name} onChange={e => setHabitForm({...habitForm, habit_name: e.target.value})}>
                    {HABITS.map(h => <option key={h} value={h}>{h}</option>)}
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: '1rem' }}>
                  <label className="form-label">Completion Status</label>
                  <select className="form-select" value={habitForm.completed} onChange={e => setHabitForm({...habitForm, completed: e.target.value})}>
                    <option value={1}>Completed (1)</option>
                    <option value={0}>Missed (0)</option>
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: '1.5rem' }}>
                  <label className="form-label">Notes</label>
                  <input type="text" placeholder="e.g., Hard workout, read 15 pages" className="form-input" value={habitForm.notes} onChange={e => setHabitForm({...habitForm, notes: e.target.value})} />
                </div>
                <button type="submit" className="btn-primary" style={{ width: '100%' }}>Log Habit</button>
              </form>
            </div>
          </div>
          {renderRelatedAreas("Habits")}
        </div>
      </div>
    </div>
  );
}

export default HabitsTab;
