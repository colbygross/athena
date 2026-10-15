import { useState } from 'react';

// Natural-language transaction entry ("Spent $14.50 at Chipotle..."), used by Finances and Overview.
function QuickLog({ API_BASE, showToast, onLogged, inputRef }) {
  const [nlpInput, setNlpInput] = useState('');
  const [nlpLoading, setNlpLoading] = useState(false);

  const handleNlpSubmit = async (e) => {
    e.preventDefault();
    if (!nlpInput.trim()) return;
    setNlpLoading(true);
    try {
      const res = await fetch(`${API_BASE}/finances/log-nlp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: nlpInput.trim() })
      }).then(r => r.json());

      if (res.status === 'success') {
        const p = res.parsed;
        showToast(`Logged: $${p.amount.toFixed(2)} at ${p.merchant} (${p.category})`, "success");
        setNlpInput('');
        onLogged();
      } else {
        showToast(res.detail || "Couldn't read that entry. Try rephrasing it.", "error");
      }
    } catch (err) {
      showToast("Error logging natural language transaction: " + err, "error");
    } finally {
      setNlpLoading(false);
    }
  };

  return (
    <div className="glass-panel quick-log">
      <div className="quick-log-header">
        <span className="material-symbols-outlined quick-log-icon" aria-hidden="true">auto_awesome</span>
        <label htmlFor="quick-log-input" className="quick-log-label">
          Describe a transaction
        </label>
      </div>
      <form onSubmit={handleNlpSubmit} className="quick-log-form">
        <input
          id="quick-log-input"
          ref={inputRef}
          type="text"
          className="form-input quick-log-input"
          placeholder='e.g. "Spent $14.50 at Chipotle on lunch with cash" or "Moved $100 from Checking to Savings yesterday"'
          value={nlpInput}
          onChange={e => setNlpInput(e.target.value)}
          disabled={nlpLoading}
        />
        <button
          type="submit"
          className="btn-primary quick-log-submit"
          disabled={nlpLoading || !nlpInput.trim()}
        >
          {nlpLoading ? "Parsing..." : "Log Entry"}
        </button>
      </form>
    </div>
  );
}

export default QuickLog;
