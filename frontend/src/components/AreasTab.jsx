import React from 'react';
import { LinearMarkdownRenderer } from './BriefPanel';

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
  fetchAreaContent
}) {
  return (
    <div>
      <header className="page-header">
        <h1 className="page-title text-gradient-purple glitch-text">Areas Explorer</h1>
        <p className="page-subtitle">Obsidian Vault: Life Domains</p>
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
                style={{ fontSize: '0.85rem' }} 
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
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No area documents archived in vault.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '420px', overflowY: 'auto', paddingRight: '0.2rem' }}>
                {["Career", "Finances", "Fitness", "Habits", "Health", "Learning"].map(cat => {
                  const catAreas = areasList.filter(a => a.category.toLowerCase() === cat.toLowerCase());
                  if (catAreas.length === 0) return null;
                  return (
                    <div key={cat} className="area-category-group" style={{ marginBottom: '1rem' }}>
                      <div style={{ 
                        fontSize: '0.75rem', 
                        fontWeight: 'bold', 
                        color: 'var(--accent-cyan)', 
                        textTransform: 'uppercase', 
                        letterSpacing: '1px', 
                        marginBottom: '0.5rem',
                        paddingLeft: '0.5rem',
                        borderLeft: '2px solid var(--accent-cyan)'
                      }}>
                        {cat}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                        {catAreas.map((area) => {
                          const isSel = selectedArea && selectedArea.category === area.category && selectedArea.filename === area.filename;
                          return (
                            <div 
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
                                border: isSel ? '1px solid var(--accent-purple)' : '1px solid transparent',
                                background: isSel ? 'rgba(188, 19, 254, 0.05)' : '',
                                boxShadow: isSel ? '0 0 10px rgba(188, 19, 254, 0.15)' : 'none',
                                padding: '0.6rem 0.8rem'
                              }}
                            >
                              <div className="item-meta">
                                <span className="item-title" style={{ fontSize: '0.8rem', color: isSel ? 'var(--accent-purple)' : 'var(--text-primary)', fontWeight: isSel ? 'bold' : 'normal' }}>
                                  📄 {area.title}
                                </span>
                                <span className="item-subtitle" style={{ fontSize: '0.65rem' }}>{area.filename}</span>
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
                  <h3 className="panel-title" style={{ color: 'var(--accent-purple)' }}>{selectedArea.filename.replace('.md', '').replace(/_/g, ' ')}</h3>
                  <span className="project-location-text" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Location: 02_Areas/{selectedArea.category}/{selectedArea.filename}</span>
                </div>
                
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {!isEditingArea ? (
                    <button 
                      className="btn-primary" 
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', height: 'auto', border: '1px solid var(--accent-purple)', background: 'transparent' }}
                      onClick={() => setIsEditingArea(true)}
                    >
                      📝 Edit Markdown
                    </button>
                  ) : (
                    <button 
                      className="btn-secondary" 
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', height: 'auto' }}
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
                        fontFamily: 'var(--font-mono)', 
                        fontSize: '0.85rem', 
                        lineHeight: '1.4', 
                        background: '#08040d', 
                        color: '#dcd3e6', 
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
              <span className="material-symbols-outlined" style={{ fontSize: '48px', marginBottom: '1rem' }}>folder_open</span>
              <p style={{ fontWeight: 600 }}>No Area Selected</p>
              <p style={{ fontSize: '0.85rem' }}>Select an area from the left index panel to view or edit its records.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AreasTab;
