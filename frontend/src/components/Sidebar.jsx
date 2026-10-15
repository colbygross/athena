import React, { useEffect, useState } from 'react';
import { NAV_SECTIONS, navLabel } from '../nav';

function Sidebar({
  sidebarCollapsed,
  toggleSidebar,
  activeTab,
  setActiveTab,
  openSettings,
  inboxCount,
  logoSrc
}) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  const timeString = now.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: true });
  const dateString = now.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });

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
          <span className="material-symbols-outlined" style={{ fontSize: 'var(--text-lg)' }} aria-hidden="true">
            {sidebarCollapsed ? "menu_open" : "menu"}
          </span>
        </button>
      </div>

      {!sidebarCollapsed && (
        <div className="sidebar-clock" aria-hidden="true">
          <span className="sidebar-clock-time">{timeString}</span>
          <span className="sidebar-clock-date">{dateString}</span>
        </div>
      )}

      <div className="nav-sections">
        {NAV_SECTIONS.map(section => (
          <div className="nav-section" key={section.id}>
            <h2 className={sidebarCollapsed ? 'nav-section-label sr-only' : 'nav-section-label'} id={`nav-section-${section.id}`}>
              {section.label}
            </h2>
            <ul className="nav-links" aria-labelledby={`nav-section-${section.id}`}>
              {section.items.map(item => {
                const text = navLabel(item, inboxCount);
                const isActive = activeTab === item.id;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      className={`nav-item ${item.accent} ${isActive ? 'active' : ''}`}
                      onClick={() => setActiveTab(item.id)}
                      aria-current={isActive ? 'page' : undefined}
                      aria-label={text}
                      title={sidebarCollapsed ? text : undefined}
                    >
                      <span className="material-symbols-outlined nav-icon" aria-hidden="true">{item.icon}</span>
                      <span className="nav-text">{item.label}</span>
                      {item.id === 'inbox' && inboxCount > 0 && (
                        <span className="nav-badge" aria-hidden="true">{inboxCount}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div className="user-avatar" aria-hidden="true">CS</div>
        <div className="user-info">
          <span className="user-name">Archer</span>
        </div>
        <button
          type="button"
          className="sidebar-settings-btn"
          onClick={openSettings}
          aria-label="Settings"
          title="Settings"
          aria-haspopup="dialog"
        >
          <span className="material-symbols-outlined" aria-hidden="true">settings</span>
        </button>
      </div>
    </nav>
  );
}

export default Sidebar;
