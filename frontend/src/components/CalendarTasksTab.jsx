import React, { useState, useEffect, useMemo } from 'react';

function CalendarTasksTab({
  tasksData = [],
  calendarData = [],
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
  API_BASE,
  isMobile = false
}) {
  // Navigation & View Mode
  const [viewMode, setViewMode] = useState('day'); // 'day', 'week', 'month'
  const [selectedCadence, setSelectedCadence] = useState('active'); // 'active', 'daily', 'weekly', 'monthly'
  const [selectedTag, setSelectedTag] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [mobileTab, setMobileTab] = useState('calendar'); // 'calendar' or 'tasks'
  
  // Google Sync state
  const [isSyncingGoogle, setIsSyncingGoogle] = useState(false);
  const [lastGoogleSync, setLastGoogleSync] = useState(null);

  // Modals state
  const [activeModal, setActiveModal] = useState(null); // 'task', 'event', 'event_detail', 'gap_popover', 'prereq_modal'
  const [modalTask, setModalTask] = useState(null);
  const [modalEvent, setModalEvent] = useState(null);
  const [activeGap, setActiveGap] = useState(null);
  const [expandedSubtasks, setExpandedSubtasks] = useState({});
  const [newSubtaskInput, setNewSubtaskInput] = useState({});

  // Ensure selectedDay defaults to today
  useEffect(() => {
    if (!selectedDay) {
      setSelectedDay(new Date());
    }
  }, [selectedDay, setSelectedDay]);

  const formatLocalDate = (date) => {
    if (!date) return '';
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  const selectedDayStr = useMemo(() => {
    return formatLocalDate(selectedDay || new Date());
  }, [selectedDay]);

  // Extract all unique event tags
  const allEventTags = useMemo(() => {
    const tagsSet = new Set(['#Work', '#DeepWork', '#Personal', '#Fitness', '#Meeting']);
    calendarData.forEach(ev => {
      let evTags = ev.tags;
      if (typeof evTags === 'string') {
        try { evTags = json.parse(evTags); } catch (e) { evTags = []; }
      }
      if (Array.isArray(evTags)) {
        evTags.forEach(t => tagsSet.add(t));
      }
    });
    return Array.from(tagsSet);
  }, [calendarData]);

  // Helper for priority sorting
  const getPriorityWeight = (priority) => {
    switch (priority?.toLowerCase()) {
      case 'high': return 3;
      case 'medium': return 2;
      case 'low': return 1;
      default: return 2;
    }
  };

  // Sort tasks: Ready tasks first, then blocked, then completed; within groups, high priority then due date
  const sortTasks = (a, b) => {
    if (a.status !== b.status) {
      return a.status === 'pending' ? -1 : 1;
    }
    // If both pending, ready tasks before blocked tasks
    if (a.status === 'pending') {
      if (a.is_blocked !== b.is_blocked) {
        return a.is_blocked ? 1 : -1;
      }
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

  // Filter tasks based on Search and Cadence
  const filteredTasks = useMemo(() => {
    let tasks = [...tasksData];

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      tasks = tasks.filter(t => 
        t.title?.toLowerCase().includes(q) || 
        t.category?.toLowerCase().includes(q)
      );
    }

    // Cadence filter
    if (selectedCadence === 'active') {
      tasks = tasks.filter(t => !t.recurrence || t.recurrence === 'none');
    } else if (selectedCadence === 'daily') {
      tasks = tasks.filter(t => t.recurrence === 'daily');
    } else if (selectedCadence === 'weekly') {
      tasks = tasks.filter(t => t.recurrence === 'weekly');
    } else if (selectedCadence === 'monthly') {
      tasks = tasks.filter(t => t.recurrence === 'monthly');
    }

    return tasks.sort(sortTasks);
  }, [tasksData, searchQuery, selectedCadence]);

  // Filter calendar events based on Search and Tag
  const filteredCalendarEvents = useMemo(() => {
    return calendarData.filter(ev => {
      // Tag filter
      if (selectedTag !== 'all') {
        let evTags = ev.tags;
        if (typeof evTags === 'string') {
          try { evTags = JSON.parse(evTags); } catch (e) { evTags = []; }
        }
        if (!Array.isArray(evTags) || !evTags.includes(selectedTag)) {
          return false;
        }
      }
      // Search filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = ev.title?.toLowerCase().includes(q);
        const matchesDesc = ev.description?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesDesc) return false;
      }
      return true;
    });
  }, [calendarData, selectedTag, searchQuery]);

  // Compute Week Days for Week View
  const weekDays = useMemo(() => {
    const base = selectedDay ? new Date(selectedDay) : new Date();
    const dayOfWeek = base.getDay(); // 0 is Sunday
    const startOfWeek = new Date(base);
    startOfWeek.setDate(base.getDate() - dayOfWeek);

    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek);
      d.setDate(startOfWeek.getDate() + i);
      days.push(d);
    }
    return days;
  }, [selectedDay]);

  // Google Calendar 2-Way Sync Handler
  const handleGoogleSync = async () => {
    setIsSyncingGoogle(true);
    try {
      const res = await fetch(`${API_BASE}/calendar/sync-google`, { method: 'POST' }).then(r => r.json());
      if (res.status === 'success') {
        setLastGoogleSync(res.synced_at || new Date().toLocaleTimeString());
        showToast("Google Calendar synced successfully!", "success");
        fetchAllData();
      } else {
        showToast("Google Calendar sync: " + (res.detail || "Unable to sync"), "info");
      }
    } catch (err) {
      showToast("Error syncing Google Calendar: " + err, "error");
    } finally {
      setIsSyncingGoogle(false);
    }
  };

  // Subtask Helpers
  const toggleSubtask = async (taskId, subtaskId, currentCompleted) => {
    try {
      await fetch(`${API_BASE}/tasks/${taskId}/subtasks/${subtaskId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_completed: !currentCompleted })
      });
      fetchAllData();
    } catch (e) {
      console.error(e);
    }
  };

  const addSubtask = async (taskId) => {
    const title = newSubtaskInput[taskId]?.trim();
    if (!title) return;
    try {
      await fetch(`${API_BASE}/tasks/${taskId}/subtasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      });
      setNewSubtaskInput(prev => ({ ...prev, [taskId]: '' }));
      fetchAllData();
    } catch (e) {
      console.error(e);
    }
  };

  const deleteSubtask = async (taskId, subtaskId) => {
    try {
      await fetch(`${API_BASE}/tasks/${taskId}/subtasks/${subtaskId}`, { method: 'DELETE' });
      fetchAllData();
    } catch (e) {
      console.error(e);
    }
  };

  // Date Navigation handlers
  const handlePrev = () => {
    if (viewMode === 'day') {
      const d = new Date(selectedDay || new Date());
      d.setDate(d.getDate() - 1);
      setSelectedDay(d);
    } else if (viewMode === 'week') {
      const d = new Date(selectedDay || new Date());
      d.setDate(d.getDate() - 7);
      setSelectedDay(d);
    } else {
      setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
    }
  };

  const handleNext = () => {
    if (viewMode === 'day') {
      const d = new Date(selectedDay || new Date());
      d.setDate(d.getDate() + 1);
      setSelectedDay(d);
    } else if (viewMode === 'week') {
      const d = new Date(selectedDay || new Date());
      d.setDate(d.getDate() + 7);
      setSelectedDay(d);
    } else {
      setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
    }
  };

  const handleToday = () => {
    const today = new Date();
    setSelectedDay(today);
    setCurrentMonth(new Date(today.getFullYear(), today.getMonth(), 1));
  };

  // Month calculation
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

  // Compute timeline gaps on the fly for Day View
  const dayTimelineHours = Array.from({ length: 15 }, (_, i) => i + 7); // 07:00 to 21:00

  const dayEvents = useMemo(() => {
    return filteredCalendarEvents.filter(ev => {
      const s = ev.start_time?.replace('T', ' ');
      return s && s.startsWith(selectedDayStr);
    }).sort((a, b) => a.start_time.localeCompare(b.start_time));
  }, [filteredCalendarEvents, selectedDayStr]);

  // Calculate gaps between dayEvents
  const computedGaps = useMemo(() => {
    if (!selectedDayStr) return [];
    const busy = [];
    dayEvents.forEach(ev => {
      const sStr = ev.start_time?.replace('T', ' ').slice(11, 16);
      const eStr = ev.end_time?.replace('T', ' ').slice(11, 16);
      if (sStr && eStr) {
        const sMins = parseInt(sStr.slice(0, 2)) * 60 + parseInt(sStr.slice(3, 5));
        const eMins = parseInt(eStr.slice(0, 2)) * 60 + parseInt(eStr.slice(3, 5));
        if (eMins > sMins) {
          busy.push({ s: sMins, e: eMins });
        }
      }
    });

    busy.sort((a, b) => a.s - b.s);
    const dayStart = 8 * 60; // 08:00
    const dayEnd = 22 * 60; // 22:00

    const gaps = [];
    let curr = dayStart;

    busy.forEach(b => {
      if (b.s > curr) {
        const dur = b.s - curr;
        if (dur >= 15) {
          const sHour = String(Math.floor(curr / 60)).padStart(2, '0');
          const sMin = String(curr % 60).padStart(2, '0');
          const eHour = String(Math.floor(b.s / 60)).padStart(2, '0');
          const eMin = String(b.s % 60).padStart(2, '0');
          gaps.push({
            start: `${sHour}:${sMin}`,
            end: `${eHour}:${eMin}`,
            startMinutes: curr,
            duration_minutes: dur
          });
        }
      }
      curr = Math.max(curr, b.e);
    });

    if (curr < dayEnd) {
      const dur = dayEnd - curr;
      if (dur >= 15) {
        const sHour = String(Math.floor(curr / 60)).padStart(2, '0');
        const sMin = String(curr % 60).padStart(2, '0');
        const eHour = String(Math.floor(dayEnd / 60)).padStart(2, '0');
        const eMin = String(dayEnd % 60).padStart(2, '0');
        gaps.push({
          start: `${sHour}:${sMin}`,
          end: `${eHour}:${eMin}`,
          startMinutes: curr,
          duration_minutes: dur
        });
      }
    }

    // Match ready tasks to each gap
    const readyTasks = tasksData.filter(t => t.status === 'pending' && !t.is_blocked);
    return gaps.map(g => {
      const matching = readyTasks.filter(t => (t.estimated_minutes || 30) <= g.duration_minutes);
      return {
        ...g,
        recommended_tasks: matching.slice(0, 5)
      };
    });
  }, [dayEvents, selectedDayStr, tasksData]);

  // Open Gap Popover
  const handleOpenGap = (gap) => {
    setActiveGap(gap);
    setActiveModal('gap_popover');
  };

  // Open Event Details Modal
  const handleOpenEventDetail = (ev) => {
    setModalEvent(ev);
    setActiveModal('event_detail');
  };

  // Header Title
  const getHeaderTitle = () => {
    if (viewMode === 'day') {
      return (selectedDay || new Date()).toLocaleDateString(undefined, { 
        weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' 
      });
    } else if (viewMode === 'week') {
      const start = weekDays[0];
      const end = weekDays[6];
      return `${start.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${end.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;
    } else {
      return currentMonth.toLocaleString('default', { month: 'long', year: 'numeric' });
    }
  };

  return (
    <div className="tab-pane active" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      
      {/* MOBILE SEGMENTED VIEW SWITCHER */}
      {isMobile && (
        <div className="mobile-segmented-control">
          <button 
            className={`mobile-segmented-btn ${mobileTab === 'calendar' ? 'active' : ''}`}
            onClick={() => setMobileTab('calendar')}
          >
            <span>📅</span> Calendar ({calendarData.length})
          </button>
          <button 
            className={`mobile-segmented-btn ${mobileTab === 'tasks' ? 'active' : ''}`}
            onClick={() => setMobileTab('tasks')}
          >
            <span>📋</span> Tasks ({tasksData.filter(t => t.status === 'pending').length})
          </button>
        </div>
      )}

      {/* TOP CONTROL BAR: SEARCH, TAGS, VIEW TOGGLE, 2-WAY SYNC */}
      <div className="glass-panel" style={{ padding: isMobile ? '0.75rem' : '0.9rem 1.25rem' }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: isMobile ? 'column' : 'row',
          flexWrap: 'wrap', 
          gap: isMobile ? '0.75rem' : '1rem', 
          justifyContent: 'space-between', 
          alignItems: isMobile ? 'stretch' : 'center' 
        }}>
          
          {/* Left: View Switcher & Navigation */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: isMobile ? '0.5rem' : '0.75rem', 
            flexWrap: 'wrap',
            justifyContent: isMobile ? 'space-between' : 'flex-start'
          }}>
            {(!isMobile || mobileTab === 'calendar') && (
              <div className="view-mode-toggle">
                <button 
                  className={`view-mode-btn ${viewMode === 'day' ? 'active' : ''}`}
                  onClick={() => setViewMode('day')}
                  style={isMobile ? { padding: '0.3rem 0.5rem', fontSize: '0.75rem' } : {}}
                >
                  Day
                </button>
                <button 
                  className={`view-mode-btn ${viewMode === 'week' ? 'active' : ''}`}
                  onClick={() => setViewMode('week')}
                  style={isMobile ? { padding: '0.3rem 0.5rem', fontSize: '0.75rem' } : {}}
                >
                  Week
                </button>
                <button 
                  className={`view-mode-btn ${viewMode === 'month' ? 'active' : ''}`}
                  onClick={() => setViewMode('month')}
                  style={isMobile ? { padding: '0.3rem 0.5rem', fontSize: '0.75rem' } : {}}
                >
                  Month
                </button>
              </div>
            )}

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <button className="btn-secondary" onClick={handlePrev} style={{ padding: '0.25rem 0.6rem' }}>◀</button>
              <button className="btn-secondary" onClick={handleToday} style={{ padding: '0.25rem 0.6rem', fontSize: '0.75rem' }}>Today</button>
              <button className="btn-secondary" onClick={handleNext} style={{ padding: '0.25rem 0.6rem' }}>▶</button>
            </div>

            <h3 style={{ 
              fontSize: isMobile ? '0.9rem' : '1rem', 
              fontWeight: 600, 
              color: 'var(--text-primary)', 
              margin: 0, 
              minWidth: isMobile ? 'auto' : '160px',
              textAlign: isMobile ? 'right' : 'left',
              flex: isMobile ? '1' : 'none'
            }}>
              {getHeaderTitle()}
            </h3>
          </div>

          {/* Right: Search, Google Sync, Quick Action Buttons */}
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '0.5rem', 
            flexWrap: 'wrap',
            width: isMobile ? '100%' : 'auto'
          }}>
            <input 
              type="text" 
              placeholder="Search events & tasks..." 
              className="form-input" 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ 
                width: isMobile ? '100%' : '180px', 
                padding: '0.35rem 0.65rem', 
                fontSize: '0.8rem' 
              }}
            />

            <div style={{ display: 'flex', width: isMobile ? '100%' : 'auto', gap: '0.5rem', justifyContent: isMobile ? 'space-between' : 'flex-start' }}>
              <button 
                className="btn-secondary" 
                onClick={handleGoogleSync}
                disabled={isSyncingGoogle}
                title={lastGoogleSync ? `Last synced: ${lastGoogleSync}` : 'Sync with Google Calendar'}
                style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '0.35rem', 
                  fontSize: '0.75rem', 
                  padding: '0.35rem 0.75rem',
                  flex: isMobile ? 1 : 'none',
                  justifyContent: 'center'
                }}
              >
                <span style={{ display: 'inline-block', transform: isSyncingGoogle ? 'rotate(360deg)' : 'none', transition: 'transform 0.8s' }}>
                  🔄
                </span>
                <span>{isSyncingGoogle ? 'Syncing...' : 'Sync'}</span>
              </button>

              <button 
                className="btn-primary" 
                onClick={() => {
                  setModalTask({
                    title: '',
                    category: 'general',
                    priority: 'medium',
                    estimated_minutes: 30,
                    recurrence: 'none',
                    due_date: selectedDayStr,
                    subtasks: []
                  });
                  setActiveModal('new_task');
                }}
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', flex: isMobile ? 1 : 'none' }}
              >
                + Task
              </button>

              <button 
                className="btn-secondary" 
                onClick={() => {
                  setModalEvent({
                    title: '',
                    description: '',
                    start_time: `${selectedDayStr} 10:00`,
                    end_time: `${selectedDayStr} 11:00`,
                    tags: [],
                    color: '#4facfe',
                    sync_to_google: true
                  });
                  setActiveModal('new_event');
                }}
                style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', flex: isMobile ? 1 : 'none' }}
              >
                + Event
              </button>
            </div>
          </div>
        </div>

        {/* Event Tags Filter Row */}
        {(!isMobile || mobileTab === 'calendar') && (
          <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem', overflowX: 'auto', paddingBottom: '2px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', whiteSpace: 'nowrap' }}>
              Tags:
            </span>
            <div className="tag-filter-bar" style={{ flexWrap: isMobile ? 'nowrap' : 'wrap', overflowX: isMobile ? 'auto' : 'visible' }}>
              <button 
                className={`tag-filter-chip ${selectedTag === 'all' ? 'active' : ''}`}
                onClick={() => setSelectedTag('all')}
              >
                All Tags
              </button>
              {allEventTags.map(tag => (
                <button 
                  key={tag}
                  className={`tag-filter-chip ${selectedTag === tag ? 'active' : ''}`}
                  onClick={() => setSelectedTag(selectedTag === tag ? 'all' : tag)}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* TWO-COLUMN WORKSPACE: LEFT (CALENDAR VIEW) / RIGHT (TASKS COMMAND CENTER) */}
      <div style={{ 
        display: isMobile ? 'flex' : 'grid', 
        flexDirection: 'column',
        gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1.25fr) minmax(0, 1fr)', 
        gap: '1.25rem' 
      }}>
        
        {/* ================= LEFT: CALENDAR VIEWS ================= */}
        {(!isMobile || mobileTab === 'calendar') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <div className="glass-panel" style={{ padding: '1rem', minHeight: '600px' }}>
            
            {/* --- 1. DAY VIEW: HOURLY TIMELINE WITH GAP RECOGNITION --- */}
            {viewMode === 'day' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-cyan)', paddingBottom: '0.5rem' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                    Hourly Schedule & Free Gaps
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    💡 Click any empty gap to view task recommendations
                  </div>
                </div>

                <div className="timeline-container">
                  {dayTimelineHours.map(hour => {
                    const hourStr = `${String(hour).padStart(2, '0')}:00`;
                    
                    // Events starting or active in this hour
                    const hourEvents = dayEvents.filter(ev => {
                      const s = ev.start_time?.replace('T', ' ').slice(11, 16);
                      if (!s) return false;
                      const h = parseInt(s.slice(0, 2));
                      return h === hour;
                    });

                    // Gaps in this hour
                    const hourGaps = computedGaps.filter(g => {
                      const sH = parseInt(g.start.slice(0, 2));
                      return sH === hour;
                    });

                    return (
                      <div key={hour} className="timeline-hour-row">
                        <div className="timeline-hour-label">{hourStr}</div>
                        <div className="timeline-hour-slot">
                          {/* Scheduled Events */}
                          {hourEvents.map(ev => {
                            const isGoogle = ev.source === 'google';
                            const evColor = ev.color || '#4facfe';
                            const tags = Array.isArray(ev.tags) ? ev.tags : [];
                            const attachedCount = ev.attached_tasks?.length || 0;

                            return (
                              <div 
                                key={ev.id} 
                                className="timeline-event-card"
                                style={{ borderLeftColor: evColor }}
                                onClick={() => handleOpenEventDetail(ev)}
                              >
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1, overflow: 'hidden' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{ev.title}</span>
                                    {isGoogle && (
                                      <span style={{ fontSize: '0.65rem', padding: '1px 4px', borderRadius: '3px', background: 'rgba(66, 133, 244, 0.2)', color: '#4285F4' }}>
                                        Google
                                      </span>
                                    )}
                                    {attachedCount > 0 && (
                                      <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(255, 255, 255, 0.1)', color: 'var(--text-secondary)' }}>
                                        📋 {attachedCount} tasks
                                      </span>
                                    )}
                                  </div>
                                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                                    🕒 {ev.start_time.slice(11, 16)} – {ev.end_time.slice(11, 16)} {ev.description ? `• ${ev.description}` : ''}
                                  </div>
                                </div>

                                {tags.length > 0 && (
                                  <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
                                    {tags.map(t => (
                                      <span key={t} style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '999px', background: 'rgba(255,255,255,0.08)', color: 'var(--text-secondary)' }}>
                                        {t}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          })}

                          {/* Empty Gap Blockers */}
                          {hourGaps.map((gap, gIdx) => (
                            <div 
                              key={`gap-${gIdx}`}
                              className="timeline-gap-block"
                              onClick={() => handleOpenGap(gap)}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
                                <span>💡</span>
                                <strong>{gap.duration_minutes}m Free Window</strong>
                                <span style={{ color: 'var(--text-muted)' }}>({gap.start} – {gap.end})</span>
                              </div>
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textDecoration: 'underline' }}>
                                {gap.recommended_tasks.length > 0 ? `View ${gap.recommended_tasks.length} recommended tasks` : 'No tasks fit'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* --- 2. WEEK VIEW: 7-DAY TIME GRID --- */}
            {viewMode === 'week' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowX: isMobile ? 'auto' : 'visible', WebkitOverflowScrolling: 'touch', paddingBottom: isMobile ? '0.5rem' : '0' }}>
                <div style={{ minWidth: isMobile ? '640px' : 'auto', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: '0.5rem', textAlign: 'center' }}>
                    {weekDays.map((day, idx) => {
                      const isSelected = formatLocalDate(day) === selectedDayStr;
                      const isToday = formatLocalDate(day) === formatLocalDate(new Date());
                      return (
                        <div 
                          key={idx}
                          onClick={() => setSelectedDay(day)}
                          style={{
                            padding: '0.5rem 0.25rem',
                            borderRadius: '6px',
                            background: isSelected ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                            border: isSelected ? '1px solid var(--text-primary)' : '1px solid var(--border-cyan)',
                            cursor: 'pointer',
                            transition: 'var(--transition-smooth)'
                          }}
                        >
                          <div style={{ fontSize: '0.7rem', color: isToday ? 'var(--accent-cyan)' : 'var(--text-muted)', fontWeight: isToday ? 'bold' : 'normal' }}>
                            {day.toLocaleDateString(undefined, { weekday: 'short' })}
                          </div>
                          <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {day.getDate()}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Week Day Columns Container */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: '0.4rem', minHeight: '480px', maxHeight: '520px', overflowY: 'auto' }}>
                    {weekDays.map((day, idx) => {
                      const dayStr = formatLocalDate(day);
                      const eventsForDay = filteredCalendarEvents.filter(ev => ev.start_time?.startsWith(dayStr));

                      return (
                        <div 
                          key={idx}
                          style={{ 
                            background: 'var(--bg-surface)', 
                            border: '1px solid var(--border-cyan)', 
                            borderRadius: '6px', 
                            padding: '0.4rem',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0.35rem'
                          }}
                        >
                          {eventsForDay.length === 0 ? (
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: '1rem' }}>
                              Free
                            </div>
                          ) : (
                            eventsForDay.map(ev => (
                              <div 
                                key={ev.id}
                                className="timeline-event-card"
                                style={{ borderLeftColor: ev.color || '#4facfe', padding: '0.3rem 0.4rem', fontSize: '0.7rem' }}
                                onClick={() => handleOpenEventDetail(ev)}
                              >
                                <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {ev.title}
                                </div>
                                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                                  {ev.start_time?.slice(11, 16)}
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* --- 3. MONTH VIEW: CLASSIC CALENDAR GRID --- */}
            {viewMode === 'month' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', textAlign: 'center', fontWeight: 'bold', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => <div key={d}>{d}</div>)}
                </div>

                <div className="calendar-grid">
                  {getDaysInMonth(currentMonth).map((day, idx) => {
                    if (!day) return <div key={idx} style={{ background: 'transparent' }} />;

                    const dayStr = formatLocalDate(day);
                    const dayEvents = filteredCalendarEvents.filter(ev => ev.start_time.startsWith(dayStr));
                    const dayTasks = tasksData.filter(t => t.due_date === dayStr);
                    const isToday = formatLocalDate(new Date()) === dayStr;
                    const isSelected = selectedDayStr === dayStr;

                    return (
                      <div 
                        key={idx}
                        className={`calendar-day-cell ${isToday ? 'today' : ''}`}
                        style={{
                          border: isSelected ? '1px solid var(--text-primary)' : '1px solid transparent',
                          cursor: 'pointer'
                        }}
                        onClick={() => {
                          setSelectedDay(day);
                        }}
                      >
                        <span className="calendar-day-num">{day.getDate()}</span>
                        <div className="calendar-events-container">
                          {dayEvents.slice(0, 2).map((ev, eIdx) => (
                            <div 
                              key={`ev-${ev.id}-${eIdx}`}
                              className="calendar-event-item"
                              style={{ borderLeftColor: ev.color || '#4facfe' }}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleOpenEventDetail(ev);
                              }}
                            >
                              <span className="event-text">{ev.title}</span>
                            </div>
                          ))}
                          {dayTasks.slice(0, 2).map((task, tIdx) => (
                            <div 
                              key={`task-${task.id}-${tIdx}`}
                              className={`calendar-task-item ${task.status === 'completed' ? 'completed' : ''} ${task.priority || 'medium'}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleTask(task.id);
                              }}
                            >
                              <span className="task-checkbox-icon">{task.status === 'completed' ? '☑' : '☐'}</span>
                              <span className="task-text">{task.title}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

          </div>
        </div>
        )}

        {/* ================= RIGHT: TASK COMMAND CENTER ================= */}
        {(!isMobile || mobileTab === 'tasks') && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="glass-panel" style={{ padding: '1rem', minHeight: '600px', display: 'flex', flexDirection: 'column' }}>
            
            {/* Header: Cadence Navigation Tabs */}
            <div className="cadence-nav">
              <button 
                className={`cadence-tab-btn ${selectedCadence === 'active' ? 'active' : ''}`}
                onClick={() => setSelectedCadence('active')}
              >
                Active Queue ({tasksData.filter(t => (!t.recurrence || t.recurrence === 'none') && t.status === 'pending').length})
              </button>
              <button 
                className={`cadence-tab-btn ${selectedCadence === 'daily' ? 'active' : ''}`}
                onClick={() => setSelectedCadence('daily')}
              >
                Daily Routines ({tasksData.filter(t => t.recurrence === 'daily' && t.status === 'pending').length})
              </button>
              <button 
                className={`cadence-tab-btn ${selectedCadence === 'weekly' ? 'active' : ''}`}
                onClick={() => setSelectedCadence('weekly')}
              >
                Weekly Goals ({tasksData.filter(t => t.recurrence === 'weekly' && t.status === 'pending').length})
              </button>
              <button 
                className={`cadence-tab-btn ${selectedCadence === 'monthly' ? 'active' : ''}`}
                onClick={() => setSelectedCadence('monthly')}
              >
                Monthly Objectives ({tasksData.filter(t => t.recurrence === 'monthly' && t.status === 'pending').length})
              </button>
            </div>

            {/* Tasks List */}
            <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.6rem', paddingRight: '0.25rem' }}>
              {filteredTasks.length === 0 ? (
                <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', padding: '2rem' }}>
                  No tasks found in this section.
                </div>
              ) : (
                filteredTasks.map(task => {
                  const isCompleted = task.status === 'completed';
                  const isBlocked = task.is_blocked;
                  const priorityColor = task.priority === 'high' ? 'var(--accent-pink)' : task.priority === 'low' ? 'var(--accent-purple)' : 'var(--accent-green)';
                  const subtasks = task.subtasks || [];
                  const completedSubtasks = subtasks.filter(s => s.is_completed).length;
                  const isExpanded = !!expandedSubtasks[task.id];

                  return (
                    <div 
                      key={task.id} 
                      className={`list-item ${isCompleted ? 'task-completed' : ''}`}
                      style={{ 
                        opacity: isCompleted ? 0.6 : 1,
                        padding: '0.65rem 0.85rem',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.4rem',
                        borderLeft: isBlocked ? '3px solid #ffaa00' : '3px solid transparent'
                      }}
                    >
                      {/* Top Row: Checkbox, Title, Badges, Delete */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, overflow: 'hidden' }}>
                          <input 
                            type="checkbox" 
                            checked={isCompleted} 
                            onChange={() => toggleTask(task.id)}
                            style={{ width: '1.05rem', height: '1.05rem', cursor: 'pointer', accentColor: 'var(--accent-purple)' }}
                          />
                          <div style={{ flex: 1, overflow: 'hidden' }}>
                            <span style={{ 
                              textDecoration: isCompleted ? 'line-through' : 'none', 
                              fontSize: '0.85rem', 
                              color: isCompleted ? 'var(--text-muted)' : 'var(--text-primary)',
                              fontWeight: 500
                            }}>
                              {task.title}
                            </span>
                          </div>
                        </div>

                        {/* Actions */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <button 
                            className="btn-danger-icon"
                            onClick={() => deleteTask(task.id)}
                            title="Delete task"
                          >
                            ×
                          </button>
                        </div>
                      </div>

                      {/* Middle Row: Duration, Priority, Due Date, Cadence Chips */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap', paddingLeft: '1.55rem' }}>
                        {/* Duration estimate */}
                        <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)' }}>
                          ⏱️ {task.estimated_minutes || 30}m
                        </span>

                        {/* Priority */}
                        <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(0,0,0,0.2)', border: `1px solid ${priorityColor}`, color: priorityColor }}>
                          {task.priority?.toUpperCase()}
                        </span>

                        {/* Due date */}
                        {task.due_date && (
                          <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)' }}>
                            📅 {task.due_date}
                          </span>
                        )}

                        {/* Recurrence */}
                        {task.recurrence && task.recurrence !== 'none' && (
                          <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(123, 97, 255, 0.15)', color: 'var(--accent-purple)' }}>
                            🔄 {task.recurrence}
                          </span>
                        )}

                        {/* Blocked Pill */}
                        {isBlocked && (
                          <span style={{ fontSize: '0.65rem', padding: '1px 6px', borderRadius: '3px', background: 'rgba(180, 83, 9, 0.15)', border: '1px solid var(--accent-yellow)', color: 'var(--accent-yellow)' }}>
                            ⏳ Waiting on: {task.unmet_prerequisites?.join(', ')}
                          </span>
                        )}

                        {/* Attached Event */}
                        {task.attached_event && (
                          <span style={{ fontSize: '0.65rem', padding: '1px 5px', borderRadius: '3px', background: 'rgba(0, 242, 254, 0.15)', color: 'var(--accent-cyan)' }}>
                            📌 Event: {task.attached_event.title}
                          </span>
                        )}

                        {/* Subtasks Progress Counter */}
                        {subtasks.length > 0 && (
                          <button 
                            onClick={() => setExpandedSubtasks(prev => ({ ...prev, [task.id]: !prev[task.id] }))}
                            style={{ 
                              background: 'transparent', 
                              border: 'none', 
                              color: 'var(--text-muted)', 
                              fontSize: '0.68rem', 
                              cursor: 'pointer',
                              padding: '1px 4px'
                            }}
                          >
                            ☑ {completedSubtasks}/{subtasks.length} subtasks {isExpanded ? '▲' : '▼'}
                          </button>
                        )}
                      </div>

                      {/* Expandable Subtasks Checklist */}
                      {isExpanded && (
                        <div style={{ paddingLeft: '1.55rem', display: 'flex', flexDirection: 'column', gap: '0.3rem', marginTop: '0.25rem' }}>
                          {subtasks.map(st => (
                            <div key={st.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.4rem', fontSize: '0.75rem' }}>
                              <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flex: 1, cursor: 'pointer' }}>
                                <input 
                                  type="checkbox" 
                                  checked={!!st.is_completed}
                                  onChange={() => toggleSubtask(task.id, st.id, st.is_completed)}
                                  style={{ accentColor: 'var(--accent-purple)' }}
                                />
                                <span style={{ textDecoration: st.is_completed ? 'line-through' : 'none', color: st.is_completed ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                                  {st.title}
                                </span>
                              </label>
                              <button 
                                className="btn-danger-icon" 
                                onClick={() => deleteSubtask(task.id, st.id)}
                                style={{ fontSize: '0.8rem' }}
                              >
                                ×
                              </button>
                            </div>
                          ))}

                          {/* Quick Add Subtask Input */}
                          <div style={{ display: 'flex', gap: '0.3rem', marginTop: '0.2rem' }}>
                            <input 
                              type="text" 
                              placeholder="Add subtask..."
                              className="form-input"
                              value={newSubtaskInput[task.id] || ''}
                              onChange={e => setNewSubtaskInput({ ...newSubtaskInput, [task.id]: e.target.value })}
                              onKeyDown={e => { if (e.key === 'Enter') addSubtask(task.id); }}
                              style={{ flex: 1, fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                            />
                            <button 
                              className="btn-secondary" 
                              onClick={() => addSubtask(task.id)}
                              style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                            >
                              +
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>

          </div>
        </div>
        )}

      </div>

      {/* ================= MODAL 1: SMART GAP POPOVER ================= */}
      {activeModal === 'gap_popover' && activeGap && (
        <div className="athena-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="athena-modal-card" onClick={e => e.stopPropagation()}>
            <div className="panel-header" style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1.2rem' }}>💡</span>
                <div>
                  <h3 className="panel-title" style={{ fontSize: '0.95rem', margin: 0 }}>
                    Free Gap: {activeGap.duration_minutes} Minutes
                  </h3>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Available window: {activeGap.start} – {activeGap.end}
                  </span>
                </div>
              </div>
              <button className="btn-danger-icon" onClick={() => setActiveModal(null)} style={{ fontSize: '1.2rem' }}>×</button>
            </div>

            <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
                Here are your unblocked tasks that fit comfortably into this {activeGap.duration_minutes}-minute time slot:
              </p>

              {activeGap.recommended_tasks?.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  No unblocked tasks with duration ≤ {activeGap.duration_minutes} minutes found.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '320px', overflowY: 'auto' }}>
                  {activeGap.recommended_tasks.map(t => (
                    <div 
                      key={t.id}
                      style={{
                        padding: '0.65rem 0.8rem',
                        borderRadius: '6px',
                        background: 'rgba(255, 255, 255, 0.04)',
                        border: '1px solid var(--border-cyan)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between'
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', flex: 1 }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {t.title}
                        </span>
                        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                          <span>⏱️ {t.estimated_minutes || 30}m</span>
                          <span>•</span>
                          <span style={{ color: t.priority === 'high' ? 'var(--accent-pink)' : 'var(--accent-green)' }}>
                            {t.priority?.toUpperCase()}
                          </span>
                        </div>
                      </div>

                      <button 
                        className="btn-primary"
                        onClick={async () => {
                          await toggleTask(t.id);
                          showToast(`Task "${t.title}" completed!`, "success");
                          setActiveModal(null);
                        }}
                        style={{ fontSize: '0.75rem', padding: '0.3rem 0.65rem' }}
                      >
                        Complete
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ borderTop: '1px solid var(--border-cyan)', paddingTop: '0.75rem', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                ℹ️ Note: Tasks stay separate from your calendar schedule. This gap helper lets you focus without cluttering your external calendar.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL 2: EVENT DETAILS ================= */}
      {activeModal === 'event_detail' && modalEvent && (
        <div className="athena-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="athena-modal-card" onClick={e => e.stopPropagation()}>
            <div className="panel-header" style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 className="panel-title" style={{ fontSize: '1rem', margin: 0 }}>{modalEvent.title}</h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  🕒 {modalEvent.start_time} – {modalEvent.end_time}
                </span>
              </div>
              <button className="btn-danger-icon" onClick={() => setActiveModal(null)} style={{ fontSize: '1.2rem' }}>×</button>
            </div>

            <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {modalEvent.description && (
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>DESCRIPTION</div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', margin: 0 }}>{modalEvent.description}</p>
                </div>
              )}

              {/* Tags */}
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>TAGS</div>
                <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                  {(modalEvent.tags || []).length === 0 ? (
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No tags attached</span>
                  ) : (
                    modalEvent.tags.map(t => (
                      <span key={t} style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: '999px', background: 'rgba(255,255,255,0.1)', color: 'var(--text-primary)' }}>
                        {t}
                      </span>
                    ))
                  )}
                </div>
              </div>

              {/* Attached Tasks */}
              <div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                  ATTACHED TASKS ({(modalEvent.attached_tasks || []).length})
                </div>
                {(modalEvent.attached_tasks || []).length === 0 ? (
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>No tasks attached to this event.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    {modalEvent.attached_tasks.map(at => (
                      <div key={at.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
                        <input 
                          type="checkbox" 
                          checked={at.status === 'completed'}
                          onChange={async () => {
                            await toggleTask(at.id);
                            fetchAllData();
                          }}
                          style={{ accentColor: 'var(--accent-purple)' }}
                        />
                        <span style={{ textDecoration: at.status === 'completed' ? 'line-through' : 'none' }}>
                          {at.title}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Event Actions */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', borderTop: '1px solid var(--border-cyan)', paddingTop: '1rem' }}>
                <button 
                  className="btn-danger"
                  onClick={async () => {
                    if (confirm("Are you sure you want to delete this event?")) {
                      await deleteCalendarEvent(modalEvent.id);
                      setActiveModal(null);
                    }
                  }}
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
                >
                  Delete Event
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ================= MODAL 3: CREATE NEW TASK ================= */}
      {activeModal === 'new_task' && (
        <div className="athena-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="athena-modal-card" onClick={e => e.stopPropagation()}>
            <div className="panel-header" style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title" style={{ fontSize: '0.95rem', margin: 0 }}>New Task</h3>
              <button className="btn-danger-icon" onClick={() => setActiveModal(null)} style={{ fontSize: '1.2rem' }}>×</button>
            </div>

            <form onSubmit={async (e) => {
              e.preventDefault();
              try {
                const res = await fetch(`${API_BASE}/tasks`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(modalTask)
                }).then(r => r.json());
                if (res.status === 'success') {
                  showToast("Task added successfully!", "success");
                  fetchAllData();
                  setActiveModal(null);
                }
              } catch (err) {
                showToast("Error adding task: " + err, "error");
              }
            }} style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              
              <div className="form-group">
                <label className="form-label">Task Title</label>
                <input 
                  type="text" 
                  placeholder="e.g., Finalize architecture slides"
                  className="form-input" 
                  value={modalTask.title} 
                  onChange={e => setModalTask({ ...modalTask, title: e.target.value })}
                  required 
                />
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Priority</label>
                  <select 
                    className="form-select"
                    value={modalTask.priority}
                    onChange={e => setModalTask({ ...modalTask, priority: e.target.value })}
                  >
                    <option value="high">🔴 High</option>
                    <option value="medium">🟡 Medium</option>
                    <option value="low">🔵 Low</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Estimated Duration</label>
                  <select 
                    className="form-select"
                    value={modalTask.estimated_minutes}
                    onChange={e => setModalTask({ ...modalTask, estimated_minutes: parseInt(e.target.value) })}
                  >
                    <option value={15}>⏱️ 15 mins</option>
                    <option value={30}>⏱️ 30 mins</option>
                    <option value={45}>⏱️ 45 mins</option>
                    <option value={60}>⏱️ 1 hour</option>
                    <option value={120}>⏱️ 2 hours</option>
                  </select>
                </div>
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Cadence (Recurrence)</label>
                  <select 
                    className="form-select"
                    value={modalTask.recurrence}
                    onChange={e => setModalTask({ ...modalTask, recurrence: e.target.value })}
                  >
                    <option value="none">One-off task</option>
                    <option value="daily">🔄 Daily</option>
                    <option value="weekly">🔄 Weekly</option>
                    <option value="monthly">🔄 Monthly</option>
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Due Date</label>
                  <input 
                    type="date" 
                    className="form-input"
                    value={modalTask.due_date || ''}
                    onChange={e => setModalTask({ ...modalTask, due_date: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Category</label>
                <select 
                  className="form-select"
                  value={modalTask.category}
                  onChange={e => setModalTask({ ...modalTask, category: e.target.value })}
                >
                  <option value="general">General</option>
                  <option value="finances">Finances</option>
                  <option value="health">Health</option>
                  <option value="fitness">Fitness</option>
                  <option value="learning">Learning</option>
                  <option value="career">Career</option>
                </select>
              </div>

              {/* Prerequisite Link (Optional) */}
              <div className="form-group">
                <label className="form-label">Prerequisite Task (Optional)</label>
                <select 
                  className="form-select"
                  value={modalTask.prerequisites?.[0]?.prerequisite_id || ''}
                  onChange={e => {
                    const id = e.target.value ? parseInt(e.target.value) : null;
                    if (id) {
                      setModalTask({
                        ...modalTask,
                        prerequisites: [{ prerequisite_type: 'task', prerequisite_id: id }]
                      });
                    } else {
                      setModalTask({ ...modalTask, prerequisites: [] });
                    }
                  }}
                >
                  <option value="">None (Ready immediately)</option>
                  {tasksData.filter(t => t.status === 'pending').map(t => (
                    <option key={t.id} value={t.id}>
                      {t.title} ({t.priority?.toUpperCase()})
                    </option>
                  ))}
                </select>
              </div>

              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.5rem' }}>
                Create Task
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ================= MODAL 4: CREATE NEW EVENT ================= */}
      {activeModal === 'new_event' && (
        <div className="athena-modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="athena-modal-card" onClick={e => e.stopPropagation()}>
            <div className="panel-header" style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title" style={{ fontSize: '0.95rem', margin: 0 }}>New Calendar Event</h3>
              <button className="btn-danger-icon" onClick={() => setActiveModal(null)} style={{ fontSize: '1.2rem' }}>×</button>
            </div>

            <form onSubmit={async (e) => {
              e.preventDefault();
              try {
                const res = await fetch(`${API_BASE}/calendar`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(modalEvent)
                }).then(r => r.json());
                if (res.status === 'success') {
                  showToast("Event created successfully!", "success");
                  fetchAllData();
                  setActiveModal(null);
                }
              } catch (err) {
                showToast("Error creating event: " + err, "error");
              }
            }} style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              
              <div className="form-group">
                <label className="form-label">Event Title</label>
                <input 
                  type="text" 
                  placeholder="e.g., Weekly Team Sync"
                  className="form-input" 
                  value={modalEvent.title} 
                  onChange={e => setModalEvent({ ...modalEvent, title: e.target.value })}
                  required 
                />
              </div>

              <div className="form-group">
                <label className="form-label">Description</label>
                <input 
                  type="text" 
                  placeholder="Meeting agenda, notes..."
                  className="form-input" 
                  value={modalEvent.description} 
                  onChange={e => setModalEvent({ ...modalEvent, description: e.target.value })}
                />
              </div>

              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Start Time</label>
                  <input 
                    type="datetime-local" 
                    className="form-input"
                    value={modalEvent.start_time.replace(' ', 'T')}
                    onChange={e => setModalEvent({ ...modalEvent, start_time: e.target.value.replace('T', ' ') })}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">End Time</label>
                  <input 
                    type="datetime-local" 
                    className="form-input"
                    value={modalEvent.end_time.replace(' ', 'T')}
                    onChange={e => setModalEvent({ ...modalEvent, end_time: e.target.value.replace('T', ' ') })}
                    required
                  />
                </div>
              </div>

              {/* Color Accent Picker */}
              <div className="form-group">
                <label className="form-label">Color Accent</label>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {['#4facfe', '#00f2fe', '#ff007f', '#7b61ff', '#39ff14', '#ffe600'].map(col => (
                    <button 
                      key={col}
                      type="button"
                      onClick={() => setModalEvent({ ...modalEvent, color: col })}
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        background: col,
                        border: modalEvent.color === col ? '2px solid white' : '1px solid transparent',
                        cursor: 'pointer'
                      }}
                    />
                  ))}
                </div>
              </div>

              {/* Tag Picker */}
              <div className="form-group">
                <label className="form-label">Tags</label>
                <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                  {['#Work', '#DeepWork', '#Personal', '#Fitness', '#Meeting'].map(tag => {
                    const active = (modalEvent.tags || []).includes(tag);
                    return (
                      <button 
                        key={tag}
                        type="button"
                        className={`tag-filter-chip ${active ? 'active' : ''}`}
                        onClick={() => {
                          const currentTags = modalEvent.tags || [];
                          if (active) {
                            setModalEvent({ ...modalEvent, tags: currentTags.filter(t => t !== tag) });
                          } else {
                            setModalEvent({ ...modalEvent, tags: [...currentTags, tag] });
                          }
                        }}
                      >
                        {tag}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2-Way Google Sync Checkbox */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: '0.25rem 0' }}>
                <input 
                  type="checkbox" 
                  id="syncGoogleCheckbox"
                  checked={!!modalEvent.sync_to_google}
                  onChange={e => setModalEvent({ ...modalEvent, sync_to_google: e.target.checked })}
                  style={{ accentColor: 'var(--accent-purple)' }}
                />
                <label htmlFor="syncGoogleCheckbox" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  Sync event to Google Calendar (2-Way)
                </label>
              </div>

              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.5rem' }}>
                Add Event
              </button>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}

export default CalendarTasksTab;
