import React, { useState } from 'react';
import { useDialog } from '../a11y';

const APPEARANCE_OPTIONS = [
  { id: 'system', label: 'System', icon: 'contrast' },
  { id: 'stark-dark', label: 'Dark', icon: 'dark_mode' },
  { id: 'stark-light', label: 'Light', icon: 'light_mode' },
];

function SettingsDialog({ open, onClose, appearance, setAppearance, isFullscreen, toggleFullscreen, showToast }) {
  const ref = useDialog(open, onClose);
  const [apiKeyInput, setApiKeyInput] = useState(() => localStorage.getItem('athena-api-key') || '');
  const canFullscreen = typeof document !== 'undefined' && document.fullscreenEnabled;

  if (!open) return null;

  const saveApiKey = (e) => {
    e.preventDefault();
    localStorage.setItem('athena-api-key', apiKeyInput);
    showToast("API key saved. Reconnecting...", "success");
    onClose();
    window.location.reload();
  };

  return (
    <div className="athena-modal-overlay" onClick={onClose}>
      <div
        ref={ref}
        className="athena-modal-card settings-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={e => e.stopPropagation()}
      >
        <div className="settings-header">
          <h2 id="settings-title" className="settings-title">Settings</h2>
          <button type="button" className="settings-close-btn" aria-label="Close settings" onClick={onClose}>
            <span className="material-symbols-outlined" aria-hidden="true">close</span>
          </button>
        </div>

        <section className="settings-section" aria-labelledby="settings-appearance">
          <h3 id="settings-appearance" className="settings-section-title">Appearance</h3>
          <div className="mobile-segmented-control" role="radiogroup" aria-labelledby="settings-appearance">
            {APPEARANCE_OPTIONS.map(option => (
              <button
                key={option.id}
                type="button"
                role="radio"
                aria-checked={appearance === option.id}
                data-autofocus={appearance === option.id ? true : undefined}
                className={`mobile-segmented-btn ${appearance === option.id ? 'active' : ''}`}
                onClick={() => setAppearance(option.id)}
              >
                <span className="material-symbols-outlined" aria-hidden="true">{option.icon}</span>
                {option.label}
              </button>
            ))}
          </div>
          <p className="settings-hint">System follows your device's light or dark setting.</p>
        </section>

        {canFullscreen && (
          <section className="settings-section" aria-labelledby="settings-display">
            <h3 id="settings-display" className="settings-section-title">Display</h3>
            <button type="button" className="btn-secondary settings-row-btn" onClick={toggleFullscreen}>
              <span className="material-symbols-outlined" aria-hidden="true">
                {isFullscreen ? 'fullscreen_exit' : 'fullscreen'}
              </span>
              {isFullscreen ? 'Exit full screen' : 'Enter full screen'}
            </button>
          </section>
        )}

        <section className="settings-section" aria-labelledby="settings-api">
          <h3 id="settings-api" className="settings-section-title">API connection</h3>
          <form onSubmit={saveApiKey} className="settings-api-form">
            <label className="form-label" htmlFor="settings-api-key">API key (X-API-Key)</label>
            <p className="settings-hint">Used to reach the backend over Tailscale or a private network.</p>
            <input
              id="settings-api-key"
              type="password"
              className="form-input"
              autoComplete="off"
              placeholder="Enter API key"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
            />
            <div className="settings-actions">
              <button type="submit" className="btn-primary">Save and reconnect</button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export default SettingsDialog;
