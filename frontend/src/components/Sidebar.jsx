import React from 'react';

function Sidebar({
  sidebarCollapsed,
  toggleSidebar,
  currentTime,
  activeTab,
  setActiveTab,
  theme,
  cycleTheme,
  isFullscreen,
  toggleFullscreen,
  setShowApiKeyModal,
  inboxCount,
  logoSrc
}) {
  const shortTimeString = currentTime.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: sidebarCollapsed ? undefined : '2-digit',
    hour12: true
  });

  const dateString = currentTime.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).toUpperCase();

  return (
    <nav className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`}>
      <div className="logo-container">
        <img src={logoSrc} className="logo-icon" alt="Athena OS Logo" />
        {!sidebarCollapsed && <span className="logo-text">ATHENA</span>}
        <button className="sidebar-toggle-btn" onClick={toggleSidebar} title={sidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}>
          <span className="material-symbols-outlined" style={{ fontSize: '1.25rem' }}>
            {sidebarCollapsed ? "menu_open" : "menu"}
          </span>
        </button>
      </div>
      
      <div className="system-clock-panel">
        <div className="clock-time">
          {shortTimeString}
        </div>
        <div className="clock-date">{dateString}</div>
      </div>
      
      <ul className="nav-links">
        <li>
          <a 
            className={`nav-item cyan ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            <span className="material-symbols-outlined nav-icon">dashboard</span> 
            <span className="nav-text">Overview</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item cyan ${activeTab === 'daily-briefs' ? 'active' : ''}`}
            onClick={() => setActiveTab('daily-briefs')}
          >
            <span className="material-symbols-outlined nav-icon">description</span> 
            <span className="nav-text">Daily Briefs</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item purple ${activeTab === 'projects' ? 'active' : ''}`}
            onClick={() => setActiveTab('projects')}
          >
            <span className="material-symbols-outlined nav-icon">folder</span> 
            <span className="nav-text">Projects Workspace</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item purple ${activeTab === 'areas' ? 'active' : ''}`}
            onClick={() => setActiveTab('areas')}
          >
            <span className="material-symbols-outlined nav-icon">folder_shared</span> 
            <span className="nav-text">Areas Explorer</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item purple ${activeTab === 'resources' ? 'active' : ''}`}
            onClick={() => setActiveTab('resources')}
          >
            <span className="material-symbols-outlined nav-icon">folder_special</span> 
            <span className="nav-text">Resources Vault</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item cyan ${activeTab === 'calendar-tasks' ? 'active' : ''}`}
            onClick={() => setActiveTab('calendar-tasks')}
          >
            <span className="material-symbols-outlined nav-icon">calendar_today</span> 
            <span className="nav-text">Calendar & Tasks</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item pink ${activeTab === 'finances' ? 'active' : ''}`}
            onClick={() => setActiveTab('finances')}
          >
            <span className="material-symbols-outlined nav-icon">attach_money</span> 
            <span className="nav-text">Finances</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item green ${activeTab === 'fitness' ? 'active' : ''}`}
            onClick={() => setActiveTab('fitness')}
          >
            <span className="material-symbols-outlined nav-icon">favorite</span> 
            <span className="nav-text">Health & Fitness</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item purple ${activeTab === 'learning' ? 'active' : ''}`}
            onClick={() => setActiveTab('learning')}
          >
            <span className="material-symbols-outlined nav-icon">school</span> 
            <span className="nav-text">Learning Tracker</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item yellow ${activeTab === 'career' ? 'active' : ''}`}
            onClick={() => setActiveTab('career')}
          >
            <span className="material-symbols-outlined nav-icon">work</span> 
            <span className="nav-text">Career Tracker</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item green ${activeTab === 'habits' ? 'active' : ''}`}
            onClick={() => setActiveTab('habits')}
          >
            <span className="material-symbols-outlined nav-icon">sync</span> 
            <span className="nav-text">Habit Streaks</span>
          </a>
        </li>
        <li>
          <a 
            className={`nav-item cyan ${activeTab === 'inbox' ? 'active' : ''}`}
            onClick={() => setActiveTab('inbox')}
          >
            <span className="material-symbols-outlined nav-icon">move_to_inbox</span> 
            <span className="nav-text">Athena Uplink ({inboxCount})</span>
          </a>
        </li>
      </ul>
      
      <div className="sidebar-toggles">
        <button
          className={`fullscreen-toggle-btn ${theme}`}
          onClick={toggleFullscreen}
          title="Toggle Fullscreen Mode"
        >
          <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>
            {isFullscreen ? 'fullscreen_exit' : 'fullscreen'}
          </span>
          {!sidebarCollapsed && <span>{isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Mode'}</span>}
        </button>
        
        <button
          className={`theme-toggle-btn ${theme}`}
          onClick={cycleTheme}
          title={`Current theme: ${theme}. Click to cycle.`}
        >
          {theme.includes('dark') ? (
            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>dark_mode</span>
          ) : (
            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>light_mode</span>
          )}
          
          {!sidebarCollapsed && (
            <>
              <div className="toggle-track">
                <div className="toggle-thumb" />
              </div>
              <span style={{ textTransform: 'capitalize' }}>{theme.replace('-', ' ')}</span>
            </>
          )}
        </button>
        
        <button
          className={`theme-toggle-btn ${theme}`}
          onClick={() => setShowApiKeyModal(true)}
          title="Configure secure API credentials connection"
        >
          <span className="material-symbols-outlined" style={{ fontSize: '1rem' }}>vpn_key</span>
          {!sidebarCollapsed && <span>API Connection</span>}
        </button>
      </div>
      
      <div className="sidebar-footer">
        <div className="user-avatar">CS</div>
        <div className="user-info">
          <span className="user-name">Archer</span>
          <span className="user-role">Neural Partner</span>
          <span className="sys-diagnostic-text">
            <span className="sys-diagnostic-dot"></span>
            [ATHENA_LINK_ON]
          </span>
        </div>
      </div>
    </nav>
  );
}

export default Sidebar;
