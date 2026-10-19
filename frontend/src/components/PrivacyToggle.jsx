import { useId, useState } from 'react';

export const PRIVACY_HINT = 'Private: only readable on this machine and by the local model; hidden from Claude and other cloud agents.';
const INTRO_KEY = 'athena-privacy-intro-seen';

const introSeen = () => {
  try { return localStorage.getItem(INTRO_KEY) === 'true'; } catch { return true; }
};
const markIntroSeen = () => {
  try { localStorage.setItem(INTRO_KEY, 'true'); } catch { /* storage unavailable */ }
};

// Vault-relative path of a note shown on the Projects, Resources or Areas tab.
export const notePath = (folder, filename, category) =>
  category && category !== '.' ? `${folder}/${category}/${filename}` : `${folder}/${filename}`;

// Small lock shown next to a private item in a list.
export function PrivateBadge() {
  return (
    <span className="private-badge" title={PRIVACY_HINT}>
      <span className="material-symbols-outlined" aria-hidden="true">lock</span>
      <span className="sr-only">Private</span>
    </span>
  );
}

// Toggle button for an item's private flag. `compact` renders an icon-only button for list rows.
export function PrivacyToggle({ isPrivate, onToggle, busy = false, disabled = false, disabledReason, compact = false, itemName }) {
  const hintId = useId();
  const [showIntro, setShowIntro] = useState(() => !compact && !introSeen());
  const label = compact ? `Private${itemName ? `: ${itemName}` : ''}` : undefined;

  // aria-disabled rather than disabled, so keyboard focus stays on the button while it saves.
  const inactive = disabled || busy;
  const handleClick = () => {
    if (inactive) return;
    if (showIntro) {
      markIntroSeen();
      setShowIntro(false);
    }
    onToggle(!isPrivate);
  };

  return (
    <span className={`privacy-toggle-wrap${compact ? ' privacy-toggle-wrap--compact' : ''}`}>
      <button
        type="button"
        className={`privacy-toggle${compact ? ' privacy-toggle--compact' : ''}${isPrivate ? ' is-private' : ''}`}
        aria-pressed={isPrivate}
        aria-label={label}
        aria-describedby={hintId}
        title={disabled && disabledReason ? disabledReason : PRIVACY_HINT}
        aria-disabled={inactive}
        aria-busy={busy}
        onClick={handleClick}
      >
        <span className="material-symbols-outlined" aria-hidden="true">{isPrivate ? 'lock' : 'lock_open'}</span>
        {!compact && <span>Private</span>}
      </button>
      <span id={hintId} className="sr-only">{disabled && disabledReason ? disabledReason : PRIVACY_HINT}</span>
      {showIntro && (
        <span className="privacy-intro" role="note">
          <span>{PRIVACY_HINT}</span>
          <button
            type="button"
            className="privacy-intro-dismiss"
            onClick={() => { markIntroSeen(); setShowIntro(false); }}
          >
            Got it
          </button>
        </span>
      )}
    </span>
  );
}
