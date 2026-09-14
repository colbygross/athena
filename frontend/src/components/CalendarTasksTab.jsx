import React from 'react';

function CalendarTasksTab({
  tasksData,
  calendarData,
  selectedDay,
  setSelectedDay,
  currentMonth,
  setCurrentMonth,
  taskForm,
  setTaskForm,
  eventForm,
  setEventForm,
  toggleTask,
  deleteTask,
  deleteCalendarEvent,
  triggerAgent,
  showToast,
  fetchAllData,
  API_BASE
}) {
  // Priority weights and sorting
  const getPriorityWeight = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 3;
      case 'medium': return 2;
      case 'low': return 1;
      default: return 2;
    }
  };

  const sortTasks = (a, b) => {
    if (a.status !== b.status) {
      return a.status === 'pending' ? -1 : 1;
    }
    const weightA = getPriorityWeight(a.priority);
    const weightB = getPriorityWeight(b.priority);
    if (weightA !== weightB) {
      return weightB - weightA;
    }
    if (a.due_date && b.due_date) {
      return a.due_date.localeCompare(b.due_date);
    }
    if (a.due_date) return -1;
    if (b.due_date) return 1;
    return b.id - a.id;
  };

  const formatLocalDate = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  const getDaysInMonth = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const totalDays = new Date(year, month + 1, 0).getDate();
    
    const days = [];
    for (let i = 0; i < firstDay; i++) {
      days.push(null);
    }
    for (let i = 1; i <= totalDays; i++) {
      days.push(new Date(year, month, i));
    }
    return days;
  };

  // Filter tasks into categories
  const datedTasks = tasksData.filter(t => t.due_date && t.due_date.trim() !== "");
  const undatedTasks = tasksData.filter(t => !t.due_date || t.due_date.trim() === "");

  const majorOperations = datedTasks.filter(t => t.importance === 'major').sort(sortTasks);
  const minorRoutines = datedTasks.filter(t => t.importance !== 'major').sort(sortTasks);

  const undatedMajor = undatedTasks.filter(t => t.importance === 'major').sort(sortTasks);
  const undatedMinor = undatedTasks.filter(t => t.importance !== 'major').sort(sortTasks);

  // Task row helper
  const renderTaskRow = (task) => {
    const isCompleted = task.status === 'completed';
    const priorityColor = task.priority === 'high' ? 'var(--accent-pink)' : task.priority === 'low' ? 'var(--accent-purple)' : 'var(--accent-green)';
    const importanceLabel = task.importance === 'major' ? 'MAJOR' : 'MINOR';
    const importanceBg = task.importance === 'major' ? 'rgba(255, 0, 127, 0.15)' : 'rgba(255,255,255,0.03)';
    const importanceBorder = task.importance === 'major' ? 'var(--accent-pink)' : 'var(--border-cyan)';
    
    return (
      <div key={task.id} className={`list-item ${isCompleted ? 'task-completed' : ''}`} style={{ opacity: isCompleted ? 0.6 : 1, padding: '0.6rem 0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, overflow: 'hidden' }}>
          <input 
            type="checkbox" 
            checked={isCompleted} 
            onChange={() => toggleTask(task.id)}
            style={{ width: '1rem', height: '1rem', cursor: 'pointer', accentColor: 'var(--accent-purple)' }}
          />
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <span style={{ textDecoration: isCompleted ? 'line-through' : 'none', fontSize: '0.85rem', color: isCompleted ? 'var(--text-muted)' : 'var(--text-primary)', fontWeight: task.importance === 'major' ? '600' : 'normal' }}>
              {task.title}
            </span>
            <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.2rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: '0.6rem', padding: '0.05rem 0.25rem', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '3px', color: 'var(--text-muted)' }}>
                {task.category?.toUpperCase()}
              </span>
              <span style={{ fontSize: '0.6rem', padding: '0.05rem 0.25rem', background: 'rgba(0,0,0,0.2)', border: `1px solid ${priorityColor}`, borderRadius: '3px', color: priorityColor }}>
                {task.priority?.toUpperCase()}
              </span>
              <span style={{ fontSize: '0.6rem', padding: '0.05rem 0.25rem', background: importanceBg, border: `1px solid ${importanceBorder}`, borderRadius: '3px', color: task.importance === 'major' ? 'var(--accent-pink)' : 'var(--text-secondary)' }}>
                {importanceLabel}
              </span>
              {task.due_date && (
                <span style={{ fontSize: '0.65rem', color: 'var(--accent-cyan)' }}>
                  📅 {task.due_date}
                </span>
              )}
              {task.source_file && (
                <span className="task-source-file-badge" style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '120px' }} title={task.source_file}>
                  📁 {task.source_file.split('/').pop()}
                </span>
              )}
            </div>
          </div>
        </div>
        <button 
          className="btn-danger-icon" 
          onClick={() => deleteTask(task.id)}
          style={{ padding: '2px 6px', fontSize: '0.9rem' }}
        >
          ×
        </button>
      </div>
    );
  };

  return (
    <div>
      <header className="page-header">
        <div className="page-header-inner">
          <div>
            <h1 className="page-title text-gradient-cyan glitch-text">Calendar & Tasks</h1>
            <p className="page-subtitle">Logistic Core: Tasks and Chronology</p>
          </div>
        </div>
      </header>

      <div className="grid-scheduler">
        {/* LEFT COLUMN: TASK BOARD */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="glass-panel" style={{ padding: '1.25rem' }}>
            <div className="panel-header" style={{ borderBottom: '1px solid var(--border-cyan)', paddingBottom: '0.5rem', marginBottom: '0.75rem' }}>
              <h3 className="panel-title" style={{ fontSize: '0.95rem' }}>Task Command Center</h3>
              <button 
                className="btn-secondary" 
                onClick={async () => {
                  await triggerAgent();
                  showToast("Athena vault-wide task scanner engaged!", "info");
                }} 
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
              >
                🔄 Scan Vault
              </button>
            </div>

            {/* Add Task Form */}
            <form onSubmit={async (e) => {
              e.preventDefault();
              try {
                const res = await fetch(`${API_BASE}/tasks`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(taskForm)
                }).then(r => r.json());
                if (res.status === 'success') {
                  setTaskForm({ title: '', category: 'general', due_date: '', priority: 'medium', importance: 'minor' });
                  fetchAllData();
                }
              } catch (err) {
                console.error("Error adding task:", err);
              }
            }} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <input 
                type="text" 
                placeholder="Add new task..." 
                className="form-input" 
                value={taskForm.title} 
                onChange={e => setTaskForm({ ...taskForm, title: e.target.value })} 
                required 
              />
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <select 
                  className="form-select" 
                  value={taskForm.category} 
                  onChange={e => setTaskForm({ ...taskForm, category: e.target.value })}
                  style={{ flex: 1, minWidth: '80px' }}
                >
                  <option value="general">General</option>
                  <option value="finances">Finances</option>
                  <option value="health">Health</option>
                  <option value="fitness">Fitness</option>
                  <option value="learning">Learning</option>
                  <option value="career">Career</option>
                </select>
                <input 
                  type="date" 
                  className="form-input" 
                  value={taskForm.due_date} 
                  onChange={e => setTaskForm({ ...taskForm, due_date: e.target.value })}
                  style={{ flex: 1.2, minWidth: '110px' }}
                />
                <select 
                  className="form-select" 
                  value={taskForm.priority} 
                  onChange={e => setTaskForm({ ...taskForm, priority: e.target.value })}
                  style={{ flex: 1, minWidth: '90px' }}
                >
                  <option value="high">🔴 High</option>
                  <option value="medium">🟡 Medium</option>
                  <option value="low">🔵 Low</option>
                </select>
                <select 
                  className="form-select" 
                  value={taskForm.importance} 
                  onChange={e => setTaskForm({ ...taskForm, importance: e.target.value })}
                  style={{ flex: 1, minWidth: '90px' }}
                >
                  <option value="major">⚡ Major</option>
                  <option value="minor">🌱 Minor</option>
                </select>
                <button type="submit" className="btn-primary" style={{ padding: '0.5rem 1rem' }}>Add</button>
              </div>
            </form>
          </div>

          {/* Pane 1: Major Operations */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="panel-header" style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title" style={{ fontSize: '0.9rem', color: 'var(--accent-pink)', margin: 0 }}>⚡ Major Operations</h3>
              <span className="badge" style={{ background: 'rgba(255, 0, 127, 0.15)', borderColor: 'var(--accent-pink)', color: 'var(--accent-pink)' }}>
                {majorOperations.filter(t => t.status === 'pending').length} Pending
              </span>
            </div>
            <div className="panel-content" style={{ maxHeight: '220px', overflowY: 'auto', padding: '0.5rem 1rem' }}>
              {majorOperations.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.8rem', padding: '1rem' }}>No active major operations.</p>
              ) : (
                <div className="item-list" style={{ gap: '0.4rem' }}>
                  {majorOperations.map(renderTaskRow)}
                </div>
              )}
            </div>
          </div>

          {/* Pane 2: Minor Routines */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="panel-header" style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title" style={{ fontSize: '0.9rem', color: 'var(--accent-cyan)', margin: 0 }}>🌱 Minor Routines</h3>
              <span className="badge" style={{ background: 'rgba(0, 242, 254, 0.15)', borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)' }}>
                {minorRoutines.filter(t => t.status === 'pending').length} Pending
              </span>
            </div>
            <div className="panel-content" style={{ maxHeight: '220px', overflowY: 'auto', padding: '0.5rem 1rem' }}>
              {minorRoutines.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.8rem', padding: '1rem' }}>No active minor routines.</p>
              ) : (
                <div className="item-list" style={{ gap: '0.4rem' }}>
                  {minorRoutines.map(renderTaskRow)}
                </div>
              )}
            </div>
          </div>

          {/* Pane 3: Backlog / Undated Vault */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="panel-header" style={{ padding: '0.75rem 1.25rem', borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title" style={{ fontSize: '0.9rem', color: 'var(--accent-purple)', margin: 0 }}>📁 Backlog / Undated Vault</h3>
              <span className="badge" style={{ background: 'rgba(123, 97, 255, 0.15)', borderColor: 'var(--accent-purple)', color: 'var(--accent-purple)' }}>
                {undatedTasks.filter(t => t.status === 'pending').length} Pending
              </span>
            </div>
            <div className="panel-content" style={{ maxHeight: '300px', overflowY: 'auto', padding: '0.75rem 1.25rem 1.25rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {undatedTasks.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.8rem', padding: '1rem' }}>Backlog is empty.</p>
              ) : (
                <>
                  {undatedMajor.length > 0 && (
                    <div>
                      <div style={{ fontSize: '0.7rem', fontWeight: 'bold', color: 'var(--accent-pink)', marginBottom: '0.35rem', letterSpacing: '0.5px' }}>
                        MAJOR BACKLOG
                      </div>
                      <div className="item-list" style={{ gap: '0.4rem' }}>
                        {undatedMajor.map(renderTaskRow)}
                      </div>
                    </div>
                  )}
                  {undatedMinor.length > 0 && (
                    <div>
                      <div style={{ fontSize: '0.7rem', fontWeight: 'bold', color: 'var(--text-secondary)', marginBottom: '0.35rem', letterSpacing: '0.5px' }}>
                        MINOR BACKLOG
                      </div>
                      <div className="item-list" style={{ gap: '0.4rem' }}>
                        {undatedMinor.map(renderTaskRow)}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: CALENDAR */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-panel" style={{ flex: 1 }}>
            {/* Calendar Navigation */}
            <div className="panel-header" style={{ marginBottom: '1.5rem' }}>
              <h3 className="panel-title">
                {currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' })}
              </h3>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button 
                  className="btn-secondary" 
                  onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1))}
                  style={{ padding: '0.25rem 0.75rem' }}
                >
                  ◀
                </button>
                <button 
                  className="btn-secondary" 
                  onClick={() => setCurrentMonth(new Date())}
                  style={{ padding: '0.25rem 0.5rem', fontSize: '0.7rem' }}
                >
                  Today
                </button>
                <button 
                  className="btn-secondary" 
                  onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1))}
                  style={{ padding: '0.25rem 0.75rem' }}
                >
                  ▶
                </button>
              </div>
            </div>

            {/* Calendar Grid */}
            <div className="panel-content">
              <div className="calendar-responsive-wrapper">
                <div className="calendar-responsive-content">
                  {/* Day Names */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', textAlign: 'center', fontWeight: 'bold', marginBottom: '0.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => <div key={d}>{d}</div>)}
                  </div>
                  
                  {/* Day Cells */}
                  <div className="calendar-grid">
                    {getDaysInMonth(currentMonth).map((day, idx) => {
                      if (!day) return <div key={idx} style={{ background: 'rgba(0,0,0,0.2)' }} />;
                      
                      const dayStr = formatLocalDate(day);
                      const dayEvents = calendarData.filter(ev => ev.start_time.startsWith(dayStr));
                      const dayTasks = tasksData.filter(t => t.due_date === dayStr);
                      const isToday = formatLocalDate(new Date()) === dayStr;
                      const isSelected = selectedDay && formatLocalDate(selectedDay) === dayStr;
                      
                      return (
                        <div 
                          key={idx} 
                          className={`calendar-day-cell ${isToday ? 'today' : ''}`}
                          style={{ 
                            border: isSelected ? '1px solid var(--accent-cyan)' : '1px solid transparent',
                            boxShadow: isSelected ? '0 0 10px rgba(0, 242, 254, 0.2)' : 'none'
                          }}
                          onClick={() => {
                            setSelectedDay(day);
                            setEventForm(prev => ({
                              ...prev,
                              start_date: dayStr,
                              end_date: dayStr
                            }));
                          }}
                        >
                          <span className="calendar-day-num">{day.getDate()}</span>
                          <div className="calendar-events-container">
                            {/* Events Preview */}
                            {dayEvents.slice(0, 2).map((ev, eIdx) => {
                              const isGoogle = ev.source === 'google';
                              return (
                                <div 
                                  key={`ev-${ev.id}-${eIdx}`} 
                                  className={`calendar-event-item ${isGoogle ? 'google' : 'local'}`}
                                  title={`[EVENT] ${ev.title}`}
                                >
                                  <span className="event-text">{ev.title}</span>
                                </div>
                              );
                            })}
                            {/* Dated Tasks Preview */}
                            {dayTasks.slice(0, 2).map((task, tIdx) => {
                              return (
                                <div 
                                  key={`task-${task.id}-${tIdx}`} 
                                  className={`calendar-task-item ${task.status === 'completed' ? 'completed' : ''} ${task.priority || 'medium'}`}
                                  title={`[TASK] ${task.title}`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleTask(task.id);
                                  }}
                                >
                                  <span className="task-checkbox-icon">{task.status === 'completed' ? '☑' : '☐'}</span>
                                  <span className="task-text" style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{task.title}</span>
                                </div>
                              );
                            })}
                            {dayEvents.length + dayTasks.length > 4 && (
                              <div className="calendar-more-indicator" style={{ fontSize: '0.55rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '2px' }}>
                                +{dayEvents.length + dayTasks.length - 4} more
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Agenda & Add Event Forms */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Selected Day Agenda (Combined events & tasks) */}
            <div className="glass-panel">
              <div className="panel-header" style={{ padding: '0.75rem 1.5rem', marginBottom: '0.75rem' }}>
                <h4 className="panel-title" style={{ fontSize: '0.85rem' }}>
                  Agenda for {selectedDay ? selectedDay.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : 'Select a Day'}
                </h4>
              </div>
              <div className="panel-content" style={{ maxHeight: '350px', overflowY: 'auto', padding: '0.5rem 1.25rem 1.25rem 1.25rem' }}>
                {selectedDay ? (
                  (() => {
                    const selectedDayStr = formatLocalDate(selectedDay);
                    const dayEvents = calendarData.filter(ev => ev.start_time.startsWith(selectedDayStr));
                    const dayTasks = tasksData.filter(t => t.due_date === selectedDayStr);
                    
                    if (dayEvents.length === 0 && dayTasks.length === 0) {
                      return <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem 0' }}>No events or tasks scheduled.</p>;
                    }
                    
                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {dayEvents.length > 0 && (
                          <div>
                            <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--accent-cyan)', borderBottom: '1px solid rgba(0, 242, 254, 0.2)', paddingBottom: '0.25rem', marginBottom: '0.5rem', fontFamily: 'var(--font-display)', letterSpacing: '0.5px' }}>
                              DAY EVENTS
                            </div>
                            <div className="item-list" style={{ gap: '0.4rem' }}>
                              {dayEvents.map((ev) => {
                                const isGoogle = ev.source === 'google';
                                const timeStr = ev.start_time.split(' ')[1] ? ev.start_time.split(' ')[1].slice(0, 5) : 'All Day';
                                return (
                                  <div key={ev.id} className="list-item" style={{ padding: '0.5rem 0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div style={{ flex: 1, overflow: 'hidden' }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <span className={`bullet-dot ${isGoogle ? 'google' : 'local'}`} />
                                        <strong style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>{ev.title}</strong>
                                      </div>
                                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px', paddingLeft: '0.8rem' }}>
                                        🕒 {timeStr} {ev.description ? `• ${ev.description}` : ''}
                                      </p>
                                    </div>
                                    {!isGoogle && (
                                      <button 
                                        className="btn-danger-icon" 
                                        onClick={() => deleteCalendarEvent(ev.id)}
                                      >
                                        ×
                                      </button>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        
                        {dayTasks.length > 0 && (
                          <div>
                            <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--accent-green)', borderBottom: '1px solid rgba(57, 255, 20, 0.2)', paddingBottom: '0.25rem', marginBottom: '0.5rem', fontFamily: 'var(--font-display)', letterSpacing: '0.5px' }}>
                              DAY TASKS
                            </div>
                            <div className="item-list" style={{ gap: '0.4rem' }}>
                              {dayTasks.map((task) => {
                                const isCompleted = task.status === 'completed';
                                const priorityColor = task.priority === 'high' ? 'var(--accent-pink)' : task.priority === 'low' ? 'var(--accent-purple)' : 'var(--accent-green)';
                                return (
                                  <div key={task.id} className={`list-item ${isCompleted ? 'task-completed' : ''}`} style={{ opacity: isCompleted ? 0.6 : 1, padding: '0.5rem 0.75rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, overflow: 'hidden' }}>
                                      <input 
                                        type="checkbox" 
                                        checked={isCompleted} 
                                        onChange={() => toggleTask(task.id)}
                                        style={{ width: '0.9rem', height: '0.9rem', cursor: 'pointer', accentColor: 'var(--accent-purple)' }}
                                      />
                                      <div style={{ flex: 1, overflow: 'hidden' }}>
                                        <span style={{ textDecoration: isCompleted ? 'line-through' : 'none', fontSize: '0.85rem', color: isCompleted ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                                          {task.title}
                                        </span>
                                        <div style={{ display: 'flex', gap: '0.3,', marginTop: '0.15rem' }}>
                                          <span style={{ fontSize: '0.55rem', padding: '0.02rem 0.2rem', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '2px', color: 'var(--text-muted)' }}>
                                            {task.category?.toUpperCase()}
                                          </span>
                                          <span style={{ fontSize: '0.55rem', padding: '0.02rem 0.2rem', background: 'rgba(0,0,0,0.2)', border: `1px solid ${priorityColor}`, borderRadius: '2px', color: priorityColor }}>
                                            {task.priority?.toUpperCase()}
                                          </span>
                                        </div>
                                      </div>
                                    </div>
                                    <button 
                                      className="btn-danger-icon" 
                                      onClick={() => deleteTask(task.id)}
                                    >
                                      ×
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()
                ) : (
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>Select a day on the calendar grid.</p>
                )}
              </div>
            </div>

            {/* Add Event Form */}
            <div className="glass-panel">
              <div className="panel-header" style={{ padding: '0.75rem 1.5rem', marginBottom: '0.75rem' }}>
                <h4 className="panel-title" style={{ fontSize: '0.85rem' }}>Add Local Event</h4>
              </div>
              <div className="panel-content">
                <form onSubmit={async (e) => {
                  e.preventDefault();
                  const payload = {
                    title: eventForm.title,
                    description: eventForm.description || null,
                    start_time: `${eventForm.start_date} ${eventForm.start_time}:00`,
                    end_time: `${eventForm.end_date} ${eventForm.end_time}:00`
                  };
                  try {
                    const res = await fetch(`${API_BASE}/calendar`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(payload)
                    }).then(r => r.json());
                    if (res.status === 'success') {
                      setEventForm({
                        title: '',
                        description: '',
                        start_date: formatLocalDate(selectedDay || new Date()),
                        start_time: '12:00',
                        end_date: formatLocalDate(selectedDay || new Date()),
                        end_time: '13:00'
                      });
                      fetchAllData();
                    }
                  } catch (err) {
                    console.error("Error adding event:", err);
                  }
                }} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div className="form-group">
                    <label className="form-label">Event Title</label>
                    <input 
                      type="text" 
                      placeholder="e.g., Sync meeting" 
                      className="form-input" 
                      value={eventForm.title} 
                      onChange={e => setEventForm({ ...eventForm, title: e.target.value })} 
                      required 
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Description</label>
                    <input 
                      type="text" 
                      placeholder="Details or notes..." 
                      className="form-input" 
                      value={eventForm.description} 
                      onChange={e => setEventForm({ ...eventForm, description: e.target.value })} 
                    />
                  </div>
                  <div className="form-grid" style={{ marginBottom: 0 }}>
                    <div className="form-group">
                      <label className="form-label">Start Date</label>
                      <input 
                        type="date" 
                        className="form-input" 
                        value={eventForm.start_date} 
                        onChange={e => setEventForm({ ...eventForm, start_date: e.target.value })} 
                        required 
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Start Time</label>
                      <input 
                        type="time" 
                        className="form-input" 
                        value={eventForm.start_time} 
                        onChange={e => setEventForm({ ...eventForm, start_time: e.target.value })} 
                        required 
                      />
                    </div>
                  </div>
                  <div className="form-grid" style={{ marginBottom: '0.5rem' }}>
                    <div className="form-group">
                      <label className="form-label">End Date</label>
                      <input 
                        type="date" 
                        className="form-input" 
                        value={eventForm.end_date} 
                        onChange={e => setEventForm({ ...eventForm, end_date: e.target.value })} 
                        required 
                      />
                    </div>
                    <div className="form-group">
                      <label className="form-label">End Time</label>
                      <input 
                        type="time" 
                        className="form-input" 
                        value={eventForm.end_time} 
                        onChange={e => setEventForm({ ...eventForm, end_time: e.target.value })} 
                        required 
                      />
                    </div>
                  </div>
                  <button type="submit" className="btn-primary" style={{ width: '100%' }}>Add Local Event</button>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CalendarTasksTab;
