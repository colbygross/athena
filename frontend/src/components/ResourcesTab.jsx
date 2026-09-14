import React from 'react';
import { LinearMarkdownRenderer } from './BriefPanel';

function ResourcesTab({
  resourcesList,
  selectedResource,
  setSelectedResource,
  resourceContent,
  setResourceContent,
  isEditingResource,
  setIsEditingResource,
  resourceSaving,
  saveResourceContent,
  fetchResourceContent
}) {
  return (
    <div>
      <header className="page-header">
        <h1 className="page-title text-gradient-purple glitch-text">Resources Vault</h1>
        <p className="page-subtitle">Obsidian Vault: Document Manager</p>
      </header>

      <div className="grid-scheduler">
        {/* Left Column: Resources Index List */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', minHeight: '520px' }}>
          <div className="panel-header" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '1rem' }}>
            <h3 className="panel-title">Resource Index</h3>
          </div>
          
          <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <input 
                type="text" 
                placeholder="Search resources..." 
                className="form-input" 
                style={{ fontSize: '0.85rem' }} 
                onChange={(e) => {
                  const term = e.target.value.toLowerCase();
                  document.querySelectorAll('.resource-list-item').forEach(item => {
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

            {resourcesList.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No resources archived in vault.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '420px', overflowY: 'auto', paddingRight: '0.2rem' }}>
                {resourcesList.map((resItem) => {
                  const isSel = selectedResource === resItem.filename;
                  return (
                    <div 
                      key={resItem.filename}
                      className="list-item resource-list-item"
                      data-title={resItem.title}
                      onClick={() => {
                        setSelectedResource(resItem.filename);
                        fetchResourceContent(resItem.filename);
                        setIsEditingResource(false);
                      }}
                      style={{ 
                        cursor: 'pointer', 
                        border: isSel ? '1px solid var(--accent-purple)' : '1px solid transparent',
                        background: isSel ? 'rgba(188, 19, 254, 0.05)' : '',
                        boxShadow: isSel ? '0 0 10px rgba(188, 19, 254, 0.15)' : 'none',
                        padding: '0.75rem 1rem'
                      }}
                    >
                      <div className="item-meta">
                        <span className="item-title" style={{ color: isSel ? 'var(--accent-purple)' : 'var(--text-primary)', fontWeight: isSel ? 'bold' : 'normal' }}>
                          📁 {resItem.title}
                        </span>
                        <span className="item-subtitle" style={{ fontSize: '0.7rem' }}>{resItem.filename}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Resource View / Edit Panel */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', minHeight: '520px' }}>
          {selectedResource ? (
            <>
              <div className="panel-header" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                  <h3 className="panel-title" style={{ color: 'var(--accent-purple)' }}>{selectedResource.replace('.md', '').replace(/_/g, ' ')}</h3>
                  <span className="project-location-text" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Location: 03_Resources/{selectedResource}</span>
                </div>
                
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {!isEditingResource ? (
                    <button 
                      className="btn-primary" 
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', height: 'auto', border: '1px solid var(--accent-purple)', background: 'transparent' }}
                      onClick={() => setIsEditingResource(true)}
                    >
                      📝 Edit Markdown
                    </button>
                  ) : (
                    <button 
                      className="btn-secondary" 
                      style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', height: 'auto' }}
                      onClick={() => {
                        setIsEditingResource(false);
                        fetchResourceContent(selectedResource);
                      }}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
              
              <div className="panel-content" style={{ marginTop: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
                {!isEditingResource ? (
                  <div className="project-view-pane" style={{ overflow: 'auto', maxHeight: '550px', paddingRight: '0.5rem' }}>
                    <LinearMarkdownRenderer content={resourceContent} />
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
                    <textarea 
                      className="form-textarea" 
                      value={resourceContent} 
                      onChange={(e) => setResourceContent(e.target.value)} 
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
                        onClick={() => saveResourceContent(selectedResource, resourceContent)}
                        disabled={resourceSaving}
                        style={{ width: '150px' }}
                      >
                        {resourceSaving ? 'Saving...' : 'Save Changes'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '300px', color: 'var(--text-muted)' }}>
              <span className="material-symbols-outlined" style={{ fontSize: '48px', marginBottom: '1rem' }}>folder_open</span>
              <p style={{ fontWeight: 600 }}>No Resource Selected</p>
              <p style={{ fontSize: '0.85rem' }}>Select a resource from the left index panel to view or edit its records.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ResourcesTab;
