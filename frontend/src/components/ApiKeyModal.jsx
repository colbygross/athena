import React from 'react';

function ApiKeyModal({ show, onClose, apiKeyInput, setApiKeyInput, showToast }) {
  if (!show) return null;

  return (
    <div className="api-key-modal-overlay" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(0,0,0,0.85)',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 9999,
      fontFamily: 'var(--font-mono)'
    }}>
      <div className="glass-panel" style={{
        width: '95%',
        maxWidth: '450px',
        background: 'var(--bg-card)',
        border: '2px solid var(--accent-pink)',
        borderRadius: 'var(--border-radius)',
        boxShadow: '0 0 25px rgba(255, 0, 127, 0.35)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden'
      }}>
        <div className="panel-header" style={{ borderBottom: '1px solid var(--border-cyan)' }}>
          <div className="panel-title" style={{ color: 'var(--accent-pink)' }}>
            <span className="material-symbols-outlined">vpn_key</span>
            [ NEURAL_LINK_API_CONFIG ]
          </div>
          <button 
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '1.2rem'
            }}
          >
            &times;
          </button>
        </div>
        
        <div className="panel-content" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            Enter your connection credentials to link this terminal to the secure backend when connecting via Tailscale or private network.
          </p>
          
          <div className="form-group">
            <label className="form-label" style={{ color: 'var(--accent-pink)' }}>API Key (X-API-Key)</label>
            <input 
              type="password"
              className="form-input"
              placeholder="Enter secure API key"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              style={{
                backgroundColor: '#000000',
                border: '1px solid var(--accent-pink)',
                color: 'var(--text-primary)',
                padding: '0.75rem',
                borderRadius: 'var(--border-radius)'
              }}
            />
          </div>
          
          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
            <button 
              className="form-input"
              onClick={onClose}
              style={{
                width: 'auto',
                padding: '0.5rem 1rem',
                backgroundColor: 'transparent',
                border: '1px solid var(--text-muted)',
                color: 'var(--text-primary)',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button 
              className="form-input"
              onClick={() => {
                localStorage.setItem('athena-api-key', apiKeyInput);
                showToast("API credentials saved! Re-connecting...", "success");
                onClose();
                window.location.reload();
              }}
              style={{
                width: 'auto',
                padding: '0.5rem 1rem',
                backgroundColor: 'var(--accent-pink)',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer',
                fontWeight: 'bold',
                boxShadow: '0 0 10px rgba(255, 0, 127, 0.4)'
              }}
            >
              Save Credentials
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ApiKeyModal;
