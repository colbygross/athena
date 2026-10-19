import React from 'react';
import { LinearMarkdownRenderer } from './BriefPanel';
import { activateOnKey } from '../a11y';
import { PrivateBadge, PrivacyToggle, notePath } from './PrivacyToggle';

const AREA_CATEGORIES = ["Career", "Finances", "Fitness", "Habits", "Health", "Learning"];

// Folders outside the usual six (a Private/ folder, say) still get listed, after them.
const otherCategories = (areasList) => [...new Set(areasList.map(a => a.category))]
  .filter(c => c !== '.' && !AREA_CATEGORIES.some(k => k.toLowerCase() === c.toLowerCase()))
  .sort();

function AreasTab({
  areasList,
  selectedArea,
  setSelectedArea,
  areaContent,
  setAreaContent,
  isEditingArea,
  setIsEditingArea,
  areaSaving,
  saveAreaContent,
  fetchAreaContent,
  privateNotes,
  privacyBusy,
  setItemPrivate
}) {
  const selectedPath = selectedArea ? notePath('02_Areas', selectedArea.filename, selectedArea.category) : null;
  return (
    <div>
      <header className="page-header page-header--compact">
        <h1 className="page-title">Areas</h1>
        <div className="page-header-meta">
          <p className="page-subtitle">Obsidian Vault: Life Domains</p>
        </div>
      </header>

      <div className="grid-scheduler">
        {/* Left Column: Areas Index List */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', minHeight: '520px' }}>
          <div className="panel-header" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '1rem' }}>
            <h3 className="panel-title">Areas Index</h3>
          </div>
          
          <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <input 
                type="text" 
                placeholder="Search documents..." 
                className="form-input" 
                style={{ fontSize: 'var(--text-sm)' }} 
                onChange={(e) => {
                  const term = e.target.value.toLowerCase();
                  document.querySelectorAll('.area-list-item').forEach(item => {
                    const title = item.dataset.title.toLowerCase();
                    if (title.includes(term)) {
                      item.style.display = 'flex';
                    } else {
                      item.style.display = 'none';
                    }
                  });
                }}
              />
            </div>

            {areasList.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>No area documents archived in vault.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '420px', overflowY: 'auto', paddingRight: '0.2rem' }}>
                {[...AREA_CATEGORIES, ...otherCategories(areasList)].map(cat => {
                  const catAreas = areasList.filter(a => a.category.toLowerCase() === cat.toLowerCase());
                  if (catAreas.length === 0) return null;
                  return (
                    <div key={cat} className="area-category-group" style={{ marginBottom: '1rem' }}>
                      <div style={{ 
                        fontSize: 'var(--text-xs)', 
                        fontWeight: 'bold', 
                        color: 'var(--accent-cyan)', 
                        textTransform: 'uppercase', 
                        letterSpacing: '1px', 
                        marginBottom: '0.5rem',
                        paddingLeft: '0.5rem',
                      }}>
                        {cat}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        {catAreas.map((area) => {
                          const isSel = selectedArea && selectedArea.category === area.category && selectedArea.filename === area.filename;
                          return (
                            <div role="button" tabIndex={0} onKeyDown={activateOnKey} 
                              key={`${area.category}-${area.filename}`}
                              className="list-item area-list-item"
                              data-title={area.title}
                              onClick={() => {
                                setSelectedArea({ category: area.category, filename: area.filename });
                                fetchAreaContent(area.category, area.filename);
                                setIsEditingArea(false);
                              }}
                              style={{ 
                                cursor: 'pointer', 
                                border: isSel ? '1px solid var(--text-secondary)' : '1px solid transparent',
                                background: isSel ? 'var(--surface-2)' : '',
                                padding: '0.6rem 0.8rem'
                              }}
                            >
                              <div className="item-meta">
                                <span className="item-title" style={{ fontSize: 'var(--text-xs)', color: isSel ? 'var(--text-secondary)' : 'var(--text-primary)', fontWeight: isSel ? 'bold' : 'normal' }}>
                                  {area.title}
                                  {privateNotes.has(notePath('02_Areas', area.filename, area.category)) && <> <PrivateBadge /></>}
                                </span>
                                <span className="item-subtitle" style={{ fontSize: 'var(--text-xs)' }}>{area.filename}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Area View / Edit Panel */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', minHeight: '520px' }}>
          {selectedArea ? (
            <>
              <div className="panel-header" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                  <h3 className="panel-title" style={{ color: 'var(--text-secondary)' }}>{selectedArea.filename.replace('.md', '').replace(/_/g, ' ')}</h3>
                  <span className="project-location-text" style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Location: 02_Areas/{selectedArea.category}/{selectedArea.filename}</span>
                </div>
                
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                  <PrivacyToggle
                    key={selectedPath}
                    isPrivate={privateNotes.has(selectedPath)}
                    busy={privacyBusy === selectedPath}
                    disabled={isEditingArea}
                    disabledReason="Save or cancel your edits before changing privacy."
                    onToggle={(next) => setItemPrivate({ path: selectedPath }, next, () => fetchAreaContent(selectedArea.category, selectedArea.filename))}
                  />
                  {!isEditingArea ? (
                    <button 
                      className="btn-primary" 
                      style={{ fontSize: 'var(--text-xs)', padding: '0.35rem 0.75rem', height: 'auto', border: '1px solid var(--text-secondary)', background: 'transparent' }}
                      onClick={() => setIsEditingArea(true)}
                    >
                      Edit markdown
                    </button>
                  ) : (
                    <button 
                      className="btn-secondary" 
                      style={{ fontSize: 'var(--text-xs)', padding: '0.35rem 0.75rem', height: 'auto' }}
                      onClick={() => {
                        setIsEditingArea(false);
                        fetchAreaContent(selectedArea.category, selectedArea.filename);
                      }}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
              
              <div className="panel-content" style={{ marginTop: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                {!isEditingArea ? (
                  <div className="project-view-pane" style={{ overflow: 'auto', maxHeight: '550px', paddingRight: '0.5rem' }}>
                    <LinearMarkdownRenderer content={areaContent} />
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
                    <textarea 
                      className="form-textarea" 
                      value={areaContent} 
                      onChange={(e) => setAreaContent(e.target.value)} 
                      style={{ 
                        flex: 1, 
                        minHeight: '380px', 
                        fontSize: 'var(--text-sm)', 
                        lineHeight: '1.4', 
                        background: 'var(--bg-surface)', 
                        color: 'var(--text-primary)', 
                        border: '1px solid var(--border-cyan)',
                        padding: '1rem',
                        borderRadius: '4px',
                        resize: 'vertical'
                      }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
                      <button 
                        className="btn-primary" 
                        onClick={() => saveAreaContent(selectedArea.category, selectedArea.filename, areaContent)}
                        disabled={areaSaving}
                        style={{ width: '150px' }}
                      >
                        {areaSaving ? 'Saving...' : 'Save Changes'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '300px', color: 'var(--text-muted)' }}>
              <span className="material-symbols-outlined" style={{ fontSize: '48px', marginBottom: '1rem' }} aria-hidden="true">folder_open</span>
              <p style={{ fontWeight: 600 }}>No Area Selected</p>
              <p style={{ fontSize: 'var(--text-sm)' }}>Select an area from the left index panel to view or edit its records.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AreasTab;
