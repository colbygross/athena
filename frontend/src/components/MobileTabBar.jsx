import React, { useState } from 'react';
import { useDialog } from '../a11y';
import { MOBILE_TABS, NAV_SECTIONS, navLabel } from '../nav';

const PRIMARY_IDS = new Set(MOBILE_TABS.map(tab => tab.id));

function MobileTabBar({ activeTab, setActiveTab, openSettings, inboxCount }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const closeMore = () => setMoreOpen(false);
  const sheetRef = useDialog(moreOpen, closeMore);
  const moreActive = !PRIMARY_IDS.has(activeTab);

  const moreSections = NAV_SECTIONS
    .map(section => ({ ...section, items: section.items.filter(item => !PRIMARY_IDS.has(item.id)) }))
    .filter(section => section.items.length > 0);

  const go = (id) => {
    setMoreOpen(false);
    setActiveTab(id);
  };

  return (
    <>
      <nav className="tab-bar" aria-label="Main">
        {MOBILE_TABS.map(tab => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              className={`tab-bar-item ${isActive ? 'active' : ''}`}
              onClick={() => go(tab.id)}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="material-symbols-outlined" aria-hidden="true">{tab.icon}</span>
              <span className="tab-bar-label">{tab.label}</span>
            </button>
          );
        })}
        <button
          type="button"
          className={`tab-bar-item ${moreActive ? 'active' : ''}`}
          onClick={() => setMoreOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={moreOpen}
          aria-label={inboxCount > 0 ? `More, ${inboxCount} in inbox` : 'More'}
        >
          <span className="material-symbols-outlined" aria-hidden="true">more_horiz</span>
          <span className="tab-bar-label">More</span>
          {inboxCount > 0 && <span className="tab-bar-badge" aria-hidden="true">{inboxCount}</span>}
        </button>
      </nav>

      {moreOpen && (
        <div className="athena-modal-overlay" onClick={closeMore}>
          <div
            ref={sheetRef}
            className="athena-modal-card more-sheet"
            role="dialog"
            aria-modal="true"
            aria-labelledby="more-sheet-title"
            onClick={e => e.stopPropagation()}
          >
            <div className="settings-header">
              <h2 id="more-sheet-title" className="settings-title">More</h2>
              <button type="button" className="settings-close-btn" aria-label="Close" onClick={closeMore}>
                <span className="material-symbols-outlined" aria-hidden="true">close</span>
              </button>
            </div>
            {moreSections.map(section => (
              <section key={section.id} className="more-sheet-section" aria-labelledby={`more-${section.id}`}>
                <h3 id={`more-${section.id}`} className="nav-section-label">{section.label}</h3>
                <ul className="more-sheet-list">
                  {section.items.map(item => {
                    const isActive = activeTab === item.id;
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          className={`nav-item ${item.accent} ${isActive ? 'active' : ''}`}
                          onClick={() => go(item.id)}
                          aria-current={isActive ? 'page' : undefined}
                          aria-label={navLabel(item, inboxCount)}
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
              </section>
            ))}
            <section className="more-sheet-section">
              <ul className="more-sheet-list">
                <li>
                  <button
                    type="button"
                    className="nav-item"
                    onClick={() => { setMoreOpen(false); openSettings(); }}
                    aria-haspopup="dialog"
                  >
                    <span className="material-symbols-outlined nav-icon" aria-hidden="true">settings</span>
                    <span className="nav-text">Settings</span>
                  </button>
                </li>
              </ul>
            </section>
          </div>
        </div>
      )}
    </>
  );
}

export default MobileTabBar;
