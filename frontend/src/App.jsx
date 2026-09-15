import { useState, useEffect } from 'react';
import archerAnarchyLogo from './assets/archer_anarchy.svg';

import ApiKeyModal from './components/ApiKeyModal';
import OverviewTab from './components/OverviewTab';
import FinancesTab from './components/FinancesTab';
import FitnessTab from './components/FitnessTab';
import LearningTab from './components/LearningTab';
import CareerTab from './components/CareerTab';
import HabitsTab from './components/HabitsTab';
import Sidebar from './components/Sidebar';
import BriefPanel from './components/BriefPanel';
import CalendarTasksTab from './components/CalendarTasksTab';
import InboxTab from './components/InboxTab';
import ProjectsTab from './components/ProjectsTab';
import ResourcesTab from './components/ResourcesTab';
import AreasTab from './components/AreasTab';

const API_BASE = import.meta.env.VITE_API_URL || (
  window.location.port === '5174'
    ? `http://${window.location.hostname}:8001/api`
    : window.location.port === '5173'
      ? `http://${window.location.hostname}:8000/api`
      : `${window.location.origin}/api`
);

// Global fetch interceptor to inject X-API-Key from localStorage
const originalFetch = window.fetch;
window.fetch = async function (input, init) {
  const apiKey = localStorage.getItem('athena-api-key') || '';
  if (apiKey) {
    const url = typeof input === 'string' ? input : (input instanceof Request ? input.url : '');
    if (url.includes('/api/')) {
      init = init || {};
      init.headers = init.headers || {};
      if (init.headers instanceof Headers) {
        init.headers.set('X-API-Key', apiKey);
      } else if (Array.isArray(init.headers)) {
        if (!init.headers.some(([k]) => k.toLowerCase() === 'x-api-key')) {
          init.headers.push(['X-API-Key', apiKey]);
        }
      } else {
        init.headers['X-API-Key'] = apiKey;
      }
    }
  }
  return originalFetch(input, init);
};

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('athena-theme') || 'stark-dark';
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    return localStorage.getItem('sidebar-collapsed') === 'true';
  });
  const [showApiKeyModal, setShowApiKeyModal] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState(() => localStorage.getItem('athena-api-key') || '');

  const toggleSidebar = () => {
    setSidebarCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('sidebar-collapsed', String(next));
      return next;
    });
  };

  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(timer);
  }, []);


  const [overviewData, setOverviewData] = useState(null);
  const [financesData, setFinancesData] = useState(null);
  const [fitnessData, setFitnessData] = useState(null);
  const [healthData, setHealthData] = useState(null);
  const [mealsData, setMealsData] = useState(null);
  const [mindfulnessData, setMindfulnessData] = useState(null);
  const [learningData, setLearningData] = useState(null);
  const [careerData, setCareerData] = useState(null);
  const [habitsData, setHabitsData] = useState(null);
  const [agentStatus, setAgentStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tasksData, setTasksData] = useState([]);
  const [calendarData, setCalendarData] = useState([]);
  const [selectedDay, setSelectedDay] = useState(new Date());
  const [currentMonth, setCurrentMonth] = useState(new Date()); // Default to the current month

  // Daily Brief States
  const [selectedBrief, setSelectedBrief] = useState(null);
  const [generatingBrief, setGeneratingBrief] = useState(false);



  // Projects Workspace States
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [projectContent, setProjectContent] = useState("");
  const [isEditingProject, setIsEditingProject] = useState(false);
  const [projectSaving, setProjectSaving] = useState(false);

  // Resources Vault States
  const [resourcesList, setResourcesList] = useState([]);
  const [selectedResource, setSelectedResource] = useState(null);
  const [resourceContent, setResourceContent] = useState("");
  const [isEditingResource, setIsEditingResource] = useState(false);
  const [resourceSaving, setResourceSaving] = useState(false);

  // Areas Workspace States
  const [areasList, setAreasList] = useState([]);
  const [selectedArea, setSelectedArea] = useState(null); // { category, filename }
  const [areaContent, setAreaContent] = useState("");
  const [isEditingArea, setIsEditingArea] = useState(false);
  const [areaSaving, setAreaSaving] = useState(false);


  const [taskForm, setTaskForm] = useState({ title: '', category: 'general', due_date: '', priority: 'medium', importance: 'minor' });
  const [eventForm, setEventForm] = useState({ title: '', description: '', start_date: new Date().toISOString().split('T')[0], start_time: '12:00', end_date: new Date().toISOString().split('T')[0], end_time: '13:00' });

  // Filter and panel toggle states
  const [filterAccount, setFilterAccount] = useState('');
  const [filterDateRange, setFilterDateRange] = useState('all');
  const [toasts, setToasts] = useState([]);

  const showToast = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };


  const fetchAndSelectBrief = async (date) => {
    try {
      const res = await fetch(`${API_BASE}/daily-briefs/${date}`).then(r => r.json());
      setSelectedBrief(res);
    } catch (e) {
      console.error("Error fetching brief details:", e);
    }
  };

  const handleGenerateBrief = async () => {
    setGeneratingBrief(true);
    try {
      const res = await fetch(`${API_BASE}/daily-briefs/generate`, { method: 'POST' }).then(r => r.json());
      if (res.status === 'success') {
        showToast("Daily brief generated successfully!", "success");
        await fetch(`${API_BASE}/daily-briefs`);
        // dailyBriefsList updated in vault
        if (res.date) {
          fetchAndSelectBrief(res.date);
        }
      }
    } catch (e) {
      console.error(e);
      showToast("Failed to generate daily brief.", "error");
    } finally {
      setGeneratingBrief(false);
    }
  };

  const fetchFinances = async () => {
    try {
      let url = `${API_BASE}/finances?`;
      if (filterAccount) url += `account_id=${filterAccount}&`;
      if (filterDateRange) url += `date_range=${filterDateRange}&`;
      const res = await fetch(url).then(r => r.json());
      setFinancesData(res);
    } catch (e) {
      console.error("Error fetching finances:", e);
    }
  };

  useEffect(() => {
    if (overviewData) {
      fetchFinances();
    }
  }, [filterAccount, filterDateRange]);

  const fetchProjectContent = async (filename) => {
    try {
      const res = await fetch(`${API_BASE}/projects/${filename}`).then(r => r.json());
      setProjectContent(res.content);
    } catch (err) {
      console.error("Error fetching project content:", err);
    }
  };

  const saveProjectContent = async (filename, content) => {
    setProjectSaving(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${filename}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content })
      }).then(r => r.json());
      
      if (res.status === "success") {
        setProjectContent(content);
        setIsEditingProject(false);
        setTimeout(async () => {
          const tskRes = await fetch(`${API_BASE}/tasks`).then(r => r.json()).catch(() => ({ tasks: [] }));
          setTasksData(tskRes.tasks || []);
        }, 1000);
      }
    } catch (err) {
      console.error("Error saving project:", err);
    } finally {
      setProjectSaving(false);
    }
  };

  const fetchResourceContent = async (filename) => {
    try {
      const res = await fetch(`${API_BASE}/resources/${filename}`).then(r => r.json());
      setResourceContent(res.content);
    } catch (err) {
      console.error("Error fetching resource content:", err);
    }
  };

  const saveResourceContent = async (filename, content) => {
    setResourceSaving(true);
    try {
      const res = await fetch(`${API_BASE}/resources/${filename}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content })
      }).then(r => r.json());
      
      if (res.status === "success") {
        setResourceContent(content);
        setIsEditingResource(false);
        setTimeout(async () => {
          const tskRes = await fetch(`${API_BASE}/tasks`).then(r => r.json()).catch(() => ({ tasks: [] }));
          setTasksData(tskRes.tasks || []);
        }, 1000);
      }
    } catch (err) {
      console.error("Error saving resource:", err);
    } finally {
      setResourceSaving(false);
    }
  };

  const fetchAreaContent = async (category, filename) => {
    try {
      const res = await fetch(`${API_BASE}/areas/${category}/${filename}`).then(r => r.json());
      setAreaContent(res.content);
    } catch (err) {
      console.error("Error fetching area content:", err);
    }
  };

  const saveAreaContent = async (category, filename, content) => {
    setAreaSaving(true);
    try {
      const res = await fetch(`${API_BASE}/areas/${category}/${filename}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content })
      }).then(r => r.json());
      
      if (res.status === "success") {
        setAreaContent(content);
        setIsEditingArea(false);
        setTimeout(async () => {
          const tskRes = await fetch(`${API_BASE}/tasks`).then(r => r.json()).catch(() => ({ tasks: [] }));
          setTasksData(tskRes.tasks || []);
        }, 1000);
      }
    } catch (err) {
      console.error("Error saving area content:", err);
    } finally {
      setAreaSaving(false);
    }
  };

  const renderRelatedAreas = (categoryName) => {
    const related = areasList.filter(area => area.category.toLowerCase() === categoryName.toLowerCase());
    if (related.length === 0) return null;
    return (
      <div className="glass-panel" style={{ padding: '1.25rem', marginTop: '1.5rem', border: '1px solid rgba(188, 19, 254, 0.15)' }}>
        <div className="panel-header" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.75rem', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="material-symbols-outlined" style={{ color: 'var(--accent-purple)', fontSize: '1.2rem' }}>folder_shared</span>
          <h4 className="panel-title" style={{ fontSize: '0.9rem', margin: 0, textTransform: 'uppercase', letterSpacing: '1px' }}>Related Documents</h4>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {related.map(item => (
            <a
              key={`${item.category}-${item.filename}`}
              onClick={() => {
                setActiveTab('areas');
                setSelectedArea({ category: item.category, filename: item.filename });
                fetchAreaContent(item.category, item.filename);
                setIsEditingArea(false);
              }}
              style={{
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                textDecoration: 'none',
                padding: '0.4rem 0.6rem',
                borderRadius: '4px',
                transition: 'background 0.2s',
              }}
              className="list-item"
            >
              <span className="material-symbols-outlined" style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>description</span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.title}</span>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>({item.category})</span>
            </a>
          ))}
        </div>
      </div>
    );
  };




  const fetchAllData = async () => {
    setLoading(true);
    try {
      const financesUrl = `${API_BASE}/finances?${filterAccount ? `account_id=${filterAccount}&` : ''}${filterDateRange ? `date_range=${filterDateRange}&` : ''}`;
      const [ovRes, finRes, fitRes, hlhRes, mealsRes, mindRes, lrnRes, carRes, habRes, agtRes, tskRes, calRes, briefListRes, projRes, resRes, areasRes] = await Promise.all([
        fetch(`${API_BASE}/overview`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch overview:", err);
          return { monthly_expense: 0.0, weekly_workouts: 0, weekly_learning_hours: 0.0, active_jobs: 0, recent_transactions: [], recent_files: [], todays_habits: [] };
        }),
        fetch(financesUrl).then(r => r.json()).catch(err => {
          console.error("Failed to fetch finances:", err);
          return { transactions: [], breakdown: [], accounts: [], net_wealth: 0.0, budgets: [], recurring: [], student_loans: [] };
        }),
        fetch(`${API_BASE}/fitness`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch fitness:", err);
          return { logs: [], stats: [] };
        }),
        fetch(`${API_BASE}/health`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch health:", err);
          return { logs: [] };
        }),
        fetch(`${API_BASE}/meals`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch meals:", err);
          return { meals: [], daily_totals: {} };
        }),
        fetch(`${API_BASE}/mindfulness`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch mindfulness:", err);
          return { mindfulness: [], daily_totals: {} };
        }),
        fetch(`${API_BASE}/learning`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch learning:", err);
          return { logs: [] };
        }),
        fetch(`${API_BASE}/career`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch career:", err);
          return { applications: [] };
        }),
        fetch(`${API_BASE}/habits`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch habits:", err);
          return { logs: [] };
        }),
        fetch(`${API_BASE}/agent/status`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch agent status:", err);
          return { status: "idle", inbox_count: 0, inbox_files: [] };
        }),
        fetch(`${API_BASE}/tasks`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch tasks:", err);
          return { tasks: [] };
        }),
        fetch(`${API_BASE}/calendar`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch calendar:", err);
          return { events: [] };
        }),
        fetch(`${API_BASE}/daily-briefs`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch daily-briefs:", err);
          return { briefs: [] };
        }),
        fetch(`${API_BASE}/projects`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch projects:", err);
          return { projects: [] };
        }),
        fetch(`${API_BASE}/resources`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch resources:", err);
          return { resources: [] };
        }),
        fetch(`${API_BASE}/areas`).then(r => r.json()).catch(err => {
          console.error("Failed to fetch areas:", err);
          return { areas: [] };
        })
      ]);

      setOverviewData(ovRes);
      setFinancesData(finRes);
      setFitnessData(fitRes);
      setHealthData(hlhRes);
      setMealsData(mealsRes || { meals: [] });
      setMindfulnessData(mindRes || { mindfulness: [] });
      setLearningData(lrnRes);
      setCareerData(carRes);
      setHabitsData(habRes);
      setAgentStatus(agtRes);
      setTasksData(tskRes.tasks || []);
      setCalendarData(calRes.events || []);
      
      const projs = projRes.projects || [];
      setProjectsList(projs);
      if (projs.length > 0) {
        setSelectedProject(projs[0].filename);
        fetchProjectContent(projs[0].filename);
      } else {
        setSelectedProject(null);
        setProjectContent("");
      }

      const resList = resRes.resources || [];
      setResourcesList(resList);
      if (resList.length > 0) {
        setSelectedResource(resList[0].filename);
        fetchResourceContent(resList[0].filename);
      } else {
        setSelectedResource(null);
        setResourceContent("");
      }
      
      const areas = areasRes.areas || [];
      setAreasList(areas);
      if (areas.length > 0) {
        setSelectedArea({ category: areas[0].category, filename: areas[0].filename });
        fetchAreaContent(areas[0].category, areas[0].filename);
      } else {
        setSelectedArea(null);
        setAreaContent("");
      }
      
      const briefs = briefListRes.briefs || [];
      // dailyBriefsList updated in vault
      
      if (briefs.length > 0) {
        const latestDate = briefs[0].date;
        const res = await fetch(`${API_BASE}/daily-briefs/${latestDate}`).then(r => r.json());
        setSelectedBrief(res);
      } else {
        setSelectedBrief(null);
      }
    } catch (err) {
      console.error("Error fetching data:", err);
    } finally {
      setLoading(false);
    }
  };

  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen()
        .then(() => setIsFullscreen(true))
        .catch((err) => {
          console.error(`Error attempting to enable fullscreen: ${err.message}`);
        });
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const cycleTheme = () => {
    setTheme(current => {
      if (current === 'stark-dark') return 'stark-light';
      if (current === 'stark-light') return 'soft-dark';
      if (current === 'soft-dark') return 'soft-light';
      return 'stark-dark';
    });
  };

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('stark-light', 'soft-dark', 'soft-light', 'stark-dark');
    if (theme !== 'stark-dark') {
      root.classList.add(theme);
    }
    localStorage.setItem('athena-theme', theme);
  }, [theme]);

  useEffect(() => {
    fetchAllData();
  }, []);

  // Poll agent status if running
  useEffect(() => {
    let interval;
    if (agentStatus?.status === 'running') {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/agent/status`).then(r => r.json());
          setAgentStatus(res);
          if (res.status === 'idle') {
            fetchAllData(); // Refresh everything once completed
          }
        } catch (e) {
          console.error(e);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [agentStatus]);

  const triggerAgent = async () => {
    try {
      await fetch(`${API_BASE}/agent/run`, { method: 'POST' });
      setAgentStatus(prev => ({ ...prev, status: 'running' }));
    } catch (e) {
      console.error(e);
    }
  };

  // Submit Handlers
  const handleFormSubmit = async (endpoint, payload, resetForm, defaultValue) => {
    try {
      const res = await fetch(`${API_BASE}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }).then(r => r.json());
      if (res.status === 'success') {
        showToast("Entry logged successfully!", "success");
        resetForm(defaultValue);
        fetchAllData();
      }
    } catch (err) {
      showToast("Error logging entry: " + err, "error");
    }
  };

  const toggleTask = async (taskId) => {
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}/toggle`, {
        method: 'PUT'
      }).then(r => r.json());
      if (res.status === 'success') {
        fetchAllData();
      }
    } catch (err) {
      console.error("Error toggling task:", err);
    }
  };

  const deleteTask = async (taskId) => {
    if (!confirm("Are you sure you want to delete this task?")) return;
    try {
      const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
        method: 'DELETE'
      }).then(r => r.json());
      if (res.status === 'success') {
        fetchAllData();
      }
    } catch (err) {
      console.error("Error deleting task:", err);
    }
  };

  const deleteCalendarEvent = async (eventId) => {
    if (!confirm("Are you sure you want to delete this event?")) return;
    try {
      const res = await fetch(`${API_BASE}/calendar/${eventId}`, {
        method: 'DELETE'
      }).then(r => r.json());
      if (res.status === 'success') {
        fetchAllData();
      }
    } catch (err) {
      console.error("Error deleting event:", err);
    }
  };



  const navigateToTab = (tab) => {
    setActiveTab(tab);
    if (tab === 'projects') setIsEditingProject(false);
    if (tab === 'areas') setIsEditingArea(false);
    if (tab === 'resources') setIsEditingResource(false);
    if (tab === 'calendar-tasks') {
      setEventForm(prev => ({
        ...prev,
        start_date: formatLocalDate(selectedDay),
        end_date: formatLocalDate(selectedDay)
      }));
    }
  };

  const formatLocalDate = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };



  const fileUrl = (relativePath) => {
    if (!relativePath) return "#";
    if (relativePath.startsWith("http") || relativePath.startsWith("obsidian://")) return relativePath;
    const cleanPath = relativePath.replace(/^obsidian_vault\//, '');
    return `obsidian://open?vault=obsidian_vault&file=${encodeURIComponent(cleanPath)}`;
  };

  if (loading && !overviewData) {
    return (
      <div style={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center', fontFamily: 'var(--font-mono)' }}>
        <h2 style={{ color: 'var(--text-secondary)' }}>Establishing link with Athena...</h2>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* Sidebar Navigation */}
      <Sidebar
        sidebarCollapsed={sidebarCollapsed}
        toggleSidebar={toggleSidebar}
        currentTime={currentTime}
        activeTab={activeTab}
        setActiveTab={navigateToTab}
        theme={theme}
        cycleTheme={cycleTheme}
        isFullscreen={isFullscreen}
        toggleFullscreen={toggleFullscreen}
        setShowApiKeyModal={setShowApiKeyModal}
        inboxCount={agentStatus?.inbox_count || 0}
        logoSrc={archerAnarchyLogo}
      />

      {/* Main Panel Content with Hologram Boot Flicker */}
      <main className={`main-content ${sidebarCollapsed ? 'collapsed' : ''} flicker-effect`} key={activeTab}>
        
        {/* TAB: CALENDAR & TASKS */}
        {activeTab === 'calendar-tasks' && (
          <CalendarTasksTab
            tasksData={tasksData}
            calendarData={calendarData}
            selectedDay={selectedDay}
            setSelectedDay={setSelectedDay}
            currentMonth={currentMonth}
            setCurrentMonth={setCurrentMonth}
            taskForm={taskForm}
            setTaskForm={setTaskForm}
            eventForm={eventForm}
            setEventForm={setEventForm}
            toggleTask={toggleTask}
            deleteTask={deleteTask}
            deleteCalendarEvent={deleteCalendarEvent}
            triggerAgent={triggerAgent}
            showToast={showToast}
            fetchAllData={fetchAllData}
            API_BASE={API_BASE}
          />
        )}

        {/* TAB: OVERVIEW */}
        {activeTab === 'overview' && (
          <OverviewTab
            overviewData={overviewData}
            setActiveTab={setActiveTab}
            fileUrl={fileUrl}
            handleFormSubmit={handleFormSubmit}
          />
        )}

        {/* TAB: FINANCES */}
        {activeTab === 'finances' && financesData && (
          <FinancesTab
            financesData={financesData}
            handleFormSubmit={handleFormSubmit}
            fetchAllData={fetchAllData}
            showToast={showToast}
            API_BASE={API_BASE}
            renderRelatedAreas={renderRelatedAreas}
            filterAccount={filterAccount}
            setFilterAccount={setFilterAccount}
            filterDateRange={filterDateRange}
            setFilterDateRange={setFilterDateRange}
          />
        )}

        {activeTab === 'fitness' && fitnessData && healthData && mealsData && mindfulnessData && (
          <FitnessTab
            fitnessData={fitnessData}
            healthData={healthData}
            mealsData={mealsData}
            mindfulnessData={mindfulnessData}
            handleFormSubmit={handleFormSubmit}
            fetchAllData={fetchAllData}
            showToast={showToast}
            API_BASE={API_BASE}
            renderRelatedAreas={renderRelatedAreas}
          />
        )}

        {/* TAB: LEARNING TRACKER */}
        {activeTab === 'learning' && (
          <LearningTab
            learningData={learningData}
            handleFormSubmit={handleFormSubmit}
            renderRelatedAreas={renderRelatedAreas}
          />
        )}

        {/* TAB: CAREER TRACKER */}
        {activeTab === 'career' && (
          <CareerTab
            careerData={careerData}
            handleFormSubmit={handleFormSubmit}
            renderRelatedAreas={renderRelatedAreas}
          />
        )}

        {/* TAB: HABIT STREAKS */}
        {activeTab === 'habits' && (
          <HabitsTab
            habitsData={habitsData}
            handleFormSubmit={handleFormSubmit}
            renderRelatedAreas={renderRelatedAreas}
          />
        )}

        {/* TAB: DAILY BRIEF */}
        {activeTab === 'daily-briefs' && (
          <BriefPanel
            selectedBrief={selectedBrief}
            generatingBrief={generatingBrief}
            handleGenerateBrief={handleGenerateBrief}
          />
        )}

        {/* TAB: FILE INBOX */}
        {activeTab === 'inbox' && agentStatus && (
          <InboxTab
            agentStatus={agentStatus}
            triggerAgent={triggerAgent}
            overviewData={overviewData}
            fileUrl={fileUrl}
          />
        )}

        {/* TAB: PROJECTS WORKSPACE */}
        {activeTab === 'projects' && (
          <ProjectsTab
            projectsList={projectsList}
            selectedProject={selectedProject}
            setSelectedProject={setSelectedProject}
            projectContent={projectContent}
            setProjectContent={setProjectContent}
            isEditingProject={isEditingProject}
            setIsEditingProject={setIsEditingProject}
            projectSaving={projectSaving}
            saveProjectContent={saveProjectContent}
            fetchProjectContent={fetchProjectContent}
          />
        )}

        {/* TAB: RESOURCES VAULT */}
        {activeTab === 'resources' && (
          <ResourcesTab
            resourcesList={resourcesList}
            selectedResource={selectedResource}
            setSelectedResource={setSelectedResource}
            resourceContent={resourceContent}
            setResourceContent={setResourceContent}
            isEditingResource={isEditingResource}
            setIsEditingResource={setIsEditingResource}
            resourceSaving={resourceSaving}
            saveResourceContent={saveResourceContent}
            fetchResourceContent={fetchResourceContent}
          />
        )}

        {/* TAB: AREAS EXPLORER */}
        {activeTab === 'areas' && (
          <AreasTab
            areasList={areasList}
            selectedArea={selectedArea}
            setSelectedArea={setSelectedArea}
            areaContent={areaContent}
            setAreaContent={setAreaContent}
            isEditingArea={isEditingArea}
            setIsEditingArea={setIsEditingArea}
            areaSaving={areaSaving}
            saveAreaContent={saveAreaContent}
            fetchAreaContent={fetchAreaContent}
          />
        )}

      </main>
      
      {/* Keyframe Pulse Styling in JS */}
      <style>{`
        @keyframes pulse {
          0% { opacity: 0.6; }
          50% { opacity: 1; }
          100% { opacity: 0.6; }
        }
      `}</style>
      {/* Toast Notification Container */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast-card ${t.type}`}>
            <span className="material-symbols-outlined toast-icon">
              {t.type === 'success' ? 'check_circle' : t.type === 'error' ? 'error' : 'info'}
            </span>
            <span className="toast-message">{t.message}</span>
            <button onClick={() => setToasts(prev => prev.filter(x => x.id !== t.id))} className="toast-close-btn">&times;</button>
          </div>
        ))}
      </div>

      <ApiKeyModal
        show={showApiKeyModal}
        onClose={() => setShowApiKeyModal(false)}
        apiKeyInput={apiKeyInput}
        setApiKeyInput={setApiKeyInput}
        showToast={showToast}
      />
    </div>
  );
}

export default App;
