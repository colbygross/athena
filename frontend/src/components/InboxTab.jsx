import React from 'react';
import { PrivacyToggle } from './PrivacyToggle';

function InboxTab({
  agentStatus,
  triggerAgent,
  overviewData,
  privateFileIds,
  privacyBusy,
  setItemPrivate,
  fileUrl
}) {
  return (
    <div>
      <header className="page-header page-header--compact">
        <h1 className="page-title">Inbox</h1>
        <div className="page-header-meta">
          <p className="page-subtitle">Sync and review incoming files</p>
        </div>
      </header>

      <div className="grid-equal-2col">
        {/* Inbox Staging Folder */}
        <div className="glass-panel">
          <div className="panel-header" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '1rem' }}>
            <div>
              <h3 className="panel-title">Incoming Datastream</h3>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Incoming data packets awaiting Athena</span>
            </div>
            <button 
              className="btn-primary" 
              onClick={triggerAgent} 
              disabled={agentStatus.status === 'running'}
              style={{ opacity: agentStatus.status === 'running' ? 0.6 : 1 }}
            >
              {agentStatus.status === 'running' ? 'Syncing…' : 'Sync now'}
            </button>
          </div>
          
          <div className="panel-content" style={{ marginTop: '1.5rem' }}>
            {agentStatus.status === 'running' && (
              <div style={{ textAlign: 'center', padding: '2rem 0', color: 'var(--accent-cyan)' }}>
                <p style={{ fontWeight: 600, animation: 'pulse 1.5s infinite' }}>Scanning files, extracting data, and organizing them…</p>
              </div>
            )}
            
            {agentStatus.inbox_files.length === 0 && agentStatus.status !== 'running' ? (
              <div className="inbox-empty-state">
                <span className="material-symbols-outlined inbox-empty-icon" style={{ fontSize: '48px' }} aria-hidden="true">inbox</span>
                <p style={{ fontWeight: 600 }}>Inbox is empty</p>
                <p style={{ fontSize: 'var(--text-sm)' }}>Add receipts, PDFs, or notes to your Vault's `Inbox/` directory to have Athena integrate them.</p>
              </div>
            ) : (
              <div className="item-list">
                {agentStatus.inbox_files.map((file, idx) => (
                  <div key={idx} className="list-item">
                    <div className="item-meta">
                      <span className="item-title">{file}</span>
                      <span className="item-subtitle">Staged for Athena</span>
                    </div>
                    <span className="material-symbols-outlined file-icon" aria-hidden="true">hourglass_empty</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Sorted files database history */}
        <div className="glass-panel">
          <div className="panel-header" style={{ borderBottom: '1px solid var(--border-glass)', paddingBottom: '1rem' }}>
            <h3 className="panel-title">Athena Action Ledger</h3>
          </div>
          <div className="panel-content" style={{ marginTop: '1.5rem' }}>
            {!overviewData || overviewData.recent_files.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>No files processed in history.</p>
            ) : (
              <div className="item-list">
                {overviewData.recent_files.map((file) => (
                  <div key={file.id} className="file-row">
                    <a 
                      href={fileUrl(file.new_path)} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="list-item" 
                      style={{ textDecoration: 'none', color: 'inherit' }}
                    >
                      <div className="item-meta">
                        <span className="item-title">{file.original_name}</span>
                        <span className="item-subtitle">Moved to: {file.new_path}</span>
                        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Processed at: {file.processed_at}</span>
                      </div>
                      <span className="material-symbols-outlined" style={{ color: 'var(--color-success)' }} aria-hidden="true">check_circle</span>
                    </a>
                    <PrivacyToggle
                      compact
                      itemName={file.original_name}
                      isPrivate={privateFileIds.has(file.id)}
                      busy={privacyBusy === `file:${file.id}`}
                      onToggle={(next) => setItemPrivate({ file_id: file.id }, next)}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default InboxTab;
