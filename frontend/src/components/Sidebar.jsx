import React from 'react';

const NAV_ITEMS = [
  { id: 'overview', icon: 'dashboard', label: 'Overview', accent: 'cyan' },
  { id: 'daily-briefs', icon: 'description', label: 'Daily Briefs', accent: 'cyan' },
  { id: 'projects', icon: 'folder', label: 'Projects Workspace', accent: 'purple' },
  { id: 'areas', icon: 'folder_shared', label: 'Areas Explorer', accent: 'purple' },
  { id: 'resources', icon: 'folder_special', label: 'Resources Vault', accent: 'purple' },
  { id: 'calendar-tasks', icon: 'calendar_today', label: 'Calendar & Tasks', accent: 'cyan' },
  { id: 'finances', icon: 'attach_money', label: 'Finances', accent: 'pink' },
  { id: 'fitness', icon: 'favorite', label: 'Health & Fitness', accent: 'green' },
  { id: 'learning', icon: 'school', label: 'Learning Tracker', accent: 'purple' },
  { id: 'career', icon: 'work', label: 'Career Tracker', accent: 'yellow' },
  { id: 'habits', icon: 'sync', label: 'Habit Streaks', accent: 'green' },
  { id: 'inbox', icon: 'move_to_inbox', label: 'Athena Uplink', accent: 'cyan' },
];

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
    <nav className={`sidebar ${sidebarCollapsed ? 'collapsed' : ''}`} aria-label="Main">
      <div className="logo-container">
        <img src={logoSrc} className="logo-icon" alt="Athena OS Logo" />
        {!sidebarCollapsed && <span className="logo-text">ATHENA</span>}
        <button
          type="button"
          className="sidebar-toggle-btn"
          onClick={toggleSidebar}
          title={sidebarCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!sidebarCollapsed}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '1.25rem' }} aria-hidden="true">
            {sidebarCollapsed ? "menu_open" : "menu"}
          </span>
        </button>
      </div>
      
      <div className="system-clock-panel" aria-hidden="true">
        <div className="clock-time">
          {shortTimeString}
        </div>
        <div className="clock-date">{dateString}</div>
      </div>
      
      <ul className="nav-links">
        {NAV_ITEMS.map(({ id, icon, label, accent }) => {
          const text = id === 'inbox' ? `${label} (${inboxCount})` : label;
          return (
            <li key={id}>
              <button
                type="button"
                className={`nav-item ${accent} ${activeTab === id ? 'active' : ''}`}
                onClick={() => setActiveTab(id)}
                aria-current={activeTab === id ? 'page' : undefined}
                aria-label={text}
                title={sidebarCollapsed ? text : undefined}
              >
                <span className="material-symbols-outlined nav-icon" aria-hidden="true">{icon}</span>
                <span className="nav-text">{text}</span>
              </button>
            </li>
          );
        })}
      </ul>
      
      <div className="sidebar-toggles">
        <button
          className={`fullscreen-toggle-btn ${theme}`}
          onClick={toggleFullscreen}
          title="Toggle Fullscreen Mode"
          aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
        >
          <span className="material-symbols-outlined" style={{ fontSize: '1rem' }} aria-hidden="true">
            {isFullscreen ? 'fullscreen_exit' : 'fullscreen'}
          </span>
          {!sidebarCollapsed && <span>{isFullscreen ? 'Exit Fullscreen' : 'Fullscreen Mode'}</span>}
        </button>
        
        <button
          className={`theme-toggle-btn ${theme}`}
          onClick={cycleTheme}
          title={`Current theme: ${theme}. Click to cycle.`}
          aria-label={`Theme: ${theme.replace('-', ' ')}. Switch theme`}
        >
          {theme.includes('dark') ? (
            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }} aria-hidden="true">dark_mode</span>
          ) : (
            <span className="material-symbols-outlined" style={{ fontSize: '1rem' }} aria-hidden="true">light_mode</span>
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
          aria-label="API connection settings"
        >
          <span className="material-symbols-outlined" style={{ fontSize: '1rem' }} aria-hidden="true">vpn_key</span>
          {!sidebarCollapsed && <span>API Connection</span>}
        </button>
      </div>
      
      <div className="sidebar-footer">
        <div className="user-avatar" aria-hidden="true">CS</div>
        <div className="user-info">
          <span className="user-name">Archer</span>
          <span className="user-role">Neural Partner</span>
          <span className="sys-diagnostic-text">
            <span className="sys-diagnostic-dot" aria-hidden="true"></span>
            [ATHENA_LINK_ON]
          </span>
        </div>
      </div>
    </nav>
  );
}

export default Sidebar;
