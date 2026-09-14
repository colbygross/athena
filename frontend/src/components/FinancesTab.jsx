import React, { useState } from 'react';

function FinancesTab({
  financesData,
  handleFormSubmit,
  fetchAllData,
  showToast,
  API_BASE,
  renderRelatedAreas,
  filterAccount,
  setFilterAccount,
  filterDateRange,
  setFilterDateRange
}) {
  const [showManagePanel, setShowManagePanel] = useState(false);
  const [nlpInput, setNlpInput] = useState('');
  const [nlpLoading, setNlpLoading] = useState(false);
  
  // Tab-specific form states
  const [txForm, setTxForm] = useState({
    date: new Date().toISOString().split('T')[0],
    amount: '',
    type: 'expense',
    category: 'food',
    merchant: '',
    description: '',
    account_id: financesData?.accounts[0]?.id || '',
    transfer_account_id: ''
  });
  
  const [accForm, setAccForm] = useState({
    name: '',
    type: 'checking',
    starting_balance: ''
  });
  
  const [budForm, setBudForm] = useState({
    category: 'food',
    limit_amount: ''
  });
  
  const [recForm, setRecForm] = useState({
    name: '',
    amount: '',
    interval: 'monthly',
    category: 'subscription',
    account_id: financesData?.accounts[0]?.id || '',
    next_due_date: new Date().toISOString().split('T')[0]
  });
  
  const [loanForm, setLoanForm] = useState({
    name: '',
    type: 'subsidized',
    balance: '',
    interest_rate: '',
    interest_accumulated: ''
  });
  
  const [editingLoanId, setEditingLoanId] = useState(null);

  // Financial Operation Helpers
  const deleteAccount = async (accountId, accountName) => {
    if (!confirm(`Are you sure you want to delete "${accountName}"? All linked transactions will have their account unlinked, and linked recurring transactions will be deleted.`)) return;
    try {
      const res = await fetch(`${API_BASE}/accounts/${accountId}`, {
        method: 'DELETE'
      }).then(r => r.json());
      if (res.status === 'success') {
        showToast("Account deleted successfully!", "success");
        fetchAllData();
      }
    } catch (err) {
      showToast("Error deleting account: " + err, "error");
    }
  };

  const payRecurring = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/recurring/${id}/pay`, { method: 'POST' }).then(r => r.json());
      if (res.status === 'success') {
        showToast(`Recurring payment logged! Next due date advanced to ${res.next_due_date}.`, "success");
        fetchAllData();
      }
    } catch (err) {
      showToast("Error processing recurring payment: " + err, "error");
    }
  };

  const deleteRecurring = async (id) => {
    if (!confirm("Are you sure you want to stop tracking this recurring transaction?")) return;
    try {
      const res = await fetch(`${API_BASE}/recurring/${id}`, { method: 'DELETE' }).then(r => r.json());
      if (res.status === 'success') {
        showToast("Recurring transaction removed.", "success");
        fetchAllData();
      }
    } catch (e) {
      showToast("Error deleting recurring transaction: " + e, "error");
    }
  };

  const deleteStudentLoan = async (loanId, loanName) => {
    if (!confirm(`Are you sure you want to delete "${loanName}"?`)) return;
    try {
      const res = await fetch(`${API_BASE}/student-loans/${loanId}`, {
        method: 'DELETE'
      }).then(r => r.json());
      if (res.status === 'success') {
        showToast("Student loan deleted successfully!", "success");
        if (editingLoanId === loanId) {
          setEditingLoanId(null);
          setLoanForm({ name: '', type: 'subsidized', balance: '', interest_rate: '', interest_accumulated: '' });
        }
        fetchAllData();
      }
    } catch (err) {
      showToast("Error deleting student loan: " + err, "error");
    }
  };

  const handleStudentLoanSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      name: loanForm.name,
      type: loanForm.type,
      balance: loanForm.balance === '' ? 0.0 : parseFloat(loanForm.balance),
      interest_rate: loanForm.interest_rate === '' ? 0.0 : parseFloat(loanForm.interest_rate),
      interest_accumulated: loanForm.interest_accumulated === '' ? 0.0 : parseFloat(loanForm.interest_accumulated)
    };
    
    try {
      let res;
      if (editingLoanId) {
        res = await fetch(`${API_BASE}/student-loans/${editingLoanId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }).then(r => r.json());
      } else {
        res = await fetch(`${API_BASE}/student-loans`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        }).then(r => r.json());
      }
      
      if (res.status === 'success') {
        showToast(editingLoanId ? "Student loan updated successfully!" : "Student loan registered successfully!", "success");
        setLoanForm({ name: '', type: 'subsidized', balance: '', interest_rate: '', interest_accumulated: '' });
        setEditingLoanId(null);
        fetchAllData();
      } else {
        showToast("Error: " + (res.detail || "Failed to save loan"), "error");
      }
    } catch (err) {
      showToast("Error saving student loan: " + err, "error");
    }
  };

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
        showToast(`✓ Logged: $${p.amount.toFixed(2)} at ${p.merchant} (${p.category})`, "success");
        setNlpInput('');
        fetchAllData();
      } else {
        showToast("Error: " + (res.detail || "Failed to parse transaction"), "error");
      }
    } catch (err) {
      showToast("Error logging natural language transaction: " + err, "error");
    } finally {
      setNlpLoading(false);
    }
  };

  if (!financesData) return null;

  return (
    <div>
      <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="page-title text-gradient-pink glitch-text">Finances</h1>
          <p className="page-subtitle">Tracking: Liquid Assets & Inflow/Outflow</p>
        </div>
        <button 
          className="btn-primary" 
          onClick={() => setShowManagePanel(prev => !prev)}
          style={{ fontSize: '0.75rem' }}
        >
          ⚙️ {showManagePanel ? "Close Configuration" : "Uplink Configuration"}
        </button>
      </header>

      {/* Natural Language AI Transaction Logger (qwen2.5-coder:3b) */}
      <div className="glass-panel" style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem', border: '1px solid rgba(0, 242, 254, 0.4)', background: 'rgba(5, 10, 25, 0.7)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
          <span className="material-symbols-outlined" style={{ fontSize: '18px', color: 'var(--accent-cyan)' }}>auto_awesome</span>
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
            NATURAL LANGUAGE LOG // qwen2.5-coder:3b
          </span>
        </div>
        <form onSubmit={handleNlpSubmit} style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            className="form-input"
            style={{ flex: 1, minWidth: '240px', padding: '0.5rem 0.8rem', fontSize: '0.85rem' }}
            placeholder='e.g. "Spent $14.50 at Chipotle on lunch with cash" or "Moved $100 from Checking to Savings yesterday"'
            value={nlpInput}
            onChange={e => setNlpInput(e.target.value)}
            disabled={nlpLoading}
          />
          <button
            type="submit"
            className="btn-primary"
            style={{ whiteSpace: 'nowrap', fontSize: '0.8rem', padding: '0.5rem 1.2rem', minWidth: '110px' }}
            disabled={nlpLoading || !nlpInput.trim()}
          >
            {nlpLoading ? "Parsing..." : "Log Entry"}
          </button>
        </form>
      </div>

      {/* Overall Wealth Section */}
      <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1.5rem', border: '1px solid var(--accent-cyan)' }}>
        <span className="stat-label" style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)' }}>NET WEALTH AUTHORITY</span>
        <span className="stat-value" style={{ fontSize: 'clamp(1.8rem, 6vw, 3rem)', color: financesData.net_wealth >= 0 ? 'var(--accent-green)' : 'var(--accent-pink)', textShadow: financesData.net_wealth >= 0 ? '0 0 15px rgba(57, 255, 20, 0.3)' : '0 0 15px rgba(255, 0, 127, 0.3)', fontFamily: 'var(--font-mono)' }}>
          ${financesData.net_wealth.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>AGGREGATED TELEMETRY ACROSS ALL ACCOUNTS</span>
      </div>

      {/* Account Slider/Grid */}
      <div className="grid-overview" style={{ marginBottom: '1.5rem', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
        {financesData.accounts.map(acc => {
          const isLiability = acc.type === 'credit_card';
          return (
            <div key={acc.id} className="glass-panel" style={{ padding: '1rem 1.25rem', border: isLiability ? '1px solid rgba(255, 0, 127, 0.3)' : '1px solid rgba(0, 242, 254, 0.3)', position: 'relative' }}>
              <span style={{ position: 'absolute', top: 0, right: 0, background: isLiability ? 'var(--accent-pink)' : 'var(--accent-cyan)', color: '#070a12', fontSize: '0.55rem', padding: '0.1rem 0.35rem', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>
                {acc.type.toUpperCase()}
              </span>
              <span className="stat-label" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem', display: 'block' }}>{acc.name}</span>
              <span className="stat-value" style={{ fontSize: '1.3rem', color: 'var(--text-primary)' }}>
                ${acc.current_balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              {showManagePanel && (
                <button 
                  onClick={() => deleteAccount(acc.id, acc.name)}
                  className="btn-delete-acc"
                  style={{
                    position: 'absolute',
                    bottom: '0.5rem',
                    right: '0.5rem',
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--accent-pink)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '4px',
                    borderRadius: '4px',
                    transition: 'all 0.2s'
                  }}
                  title={`Delete ${acc.name}`}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: '1.1rem' }}>delete</span>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Configuration Panel (Collapsible) */}
      {showManagePanel && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', marginBottom: '1.5rem', gap: '1.5rem' }}>
          {/* Panel 1: Add Account */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div className="panel-header" style={{ padding: '0 0 1rem 0', marginBottom: '1rem' }}>
              <h3 className="panel-title" style={{ fontSize: '0.85rem' }}>Register Account</h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              handleFormSubmit(
                'accounts', 
                { ...accForm, starting_balance: accForm.starting_balance === '' ? 0.0 : parseFloat(accForm.starting_balance) },
                setAccForm, 
                { name: '', type: 'checking', starting_balance: '' }
              );
            }} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Name</label>
                <input type="text" placeholder="e.g., Chase Checking" className="form-input" value={accForm.name} onChange={e => setAccForm({...accForm, name: e.target.value})} required />
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select className="form-select" value={accForm.type} onChange={e => setAccForm({...accForm, type: e.target.value})}>
                  <option value="checking">Checking (Asset)</option>
                  <option value="savings">Savings (Asset)</option>
                  <option value="cash">Cash (Asset)</option>
                  <option value="investment">Investment (Asset)</option>
                  <option value="credit_card">Credit Card (Liability)</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Starting Balance ($)</label>
                <input type="number" step="0.01" placeholder="0.00" className="form-input" value={accForm.starting_balance} onChange={e => setAccForm({...accForm, starting_balance: e.target.value})} />
              </div>
              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.5rem' }}>Add Account</button>
            </form>
          </div>

          {/* Panel 2: Set Budget */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div className="panel-header" style={{ padding: '0 0 1rem 0', marginBottom: '1rem' }}>
              <h3 className="panel-title" style={{ fontSize: '0.85rem' }}>Category Budget</h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              handleFormSubmit(
                'budgets',
                { ...budForm, limit_amount: parseFloat(budForm.limit_amount) },
                setBudForm,
                { category: 'food', limit_amount: '' }
              );
            }} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Category</label>
                <select className="form-select" value={budForm.category} onChange={e => setBudForm({...budForm, category: e.target.value})}>
                  <option value="food">Food & Groceries</option>
                  <option value="utilities">Utilities & Bills</option>
                  <option value="subscription">Subscriptions</option>
                  <option value="academic">Academic / Learning</option>
                  <option value="rent">Rent / Living</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Monthly Limit ($)</label>
                <input type="number" step="0.01" placeholder="0.00" className="form-input" value={budForm.limit_amount} onChange={e => setBudForm({...budForm, limit_amount: e.target.value})} required />
              </div>
              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '3.1rem' }}>Set Budget</button>
            </form>
          </div>

          {/* Panel 3: Add Recurring */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div className="panel-header" style={{ padding: '0 0 1rem 0', marginBottom: '1rem' }}>
              <h3 className="panel-title" style={{ fontSize: '0.85rem' }}>New Recurring Payment</h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              if (!recForm.account_id) {
                showToast("Please select an account for the recurring payment.", "error");
                return;
              }
              handleFormSubmit(
                'recurring',
                {
                  ...recForm,
                  amount: parseFloat(recForm.amount),
                  account_id: parseInt(recForm.account_id)
                },
                setRecForm,
                { name: '', amount: '', interval: 'monthly', category: 'subscription', account_id: financesData.accounts[0]?.id || '', next_due_date: new Date().toISOString().split('T')[0] }
              );
            }} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="form-grid" style={{ marginBottom: 0 }}>
                <div className="form-group">
                  <label className="form-label">Name</label>
                  <input type="text" placeholder="e.g., Spotify" className="form-input" value={recForm.name} onChange={e => setRecForm({...recForm, name: e.target.value})} required />
                </div>
                <div className="form-group">
                  <label className="form-label">Amount ($)</label>
                  <input type="number" step="0.01" placeholder="0.00" className="form-input" value={recForm.amount} onChange={e => setRecForm({...recForm, amount: e.target.value})} required />
                </div>
              </div>
              <div className="form-grid" style={{ marginBottom: 0 }}>
                <div className="form-group">
                  <label className="form-label">Interval</label>
                  <select className="form-select" value={recForm.interval} onChange={e => setRecForm({...recForm, interval: e.target.value})}>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="yearly">Yearly</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Category</label>
                  <select className="form-select" value={recForm.category} onChange={e => setRecForm({...recForm, category: e.target.value})}>
                    <option value="subscription">Subscription</option>
                    <option value="utilities">Utilities / Bills</option>
                    <option value="rent">Rent / Living</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>
              <div className="form-grid" style={{ marginBottom: 0 }}>
                <div className="form-group">
                  <label className="form-label">Debit Account</label>
                  <select className="form-select" value={recForm.account_id} onChange={e => setRecForm({...recForm, account_id: e.target.value})} required>
                    <option value="">Select Account...</option>
                    {financesData.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Next Due Date</label>
                  <input type="date" className="form-input" value={recForm.next_due_date} onChange={e => setRecForm({...recForm, next_due_date: e.target.value})} required />
                </div>
              </div>
              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.2rem' }}>Add Recurring</button>
            </form>
          </div>

          {/* Panel 4: Manage Student Loans */}
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <div className="panel-header" style={{ padding: '0 0 1rem 0', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
              <h3 className="panel-title" style={{ fontSize: '0.85rem' }}>
                {editingLoanId ? "Edit Student Loan" : "Register Student Loan"}
              </h3>
              {editingLoanId && (
                <button 
                  type="button" 
                  className="btn-secondary" 
                  onClick={() => {
                    setEditingLoanId(null);
                    setLoanForm({ name: '', type: 'subsidized', balance: '', interest_rate: '', interest_accumulated: '' });
                  }}
                  style={{ fontSize: '0.65rem', padding: '0.25rem 0.5rem', height: 'auto', border: '1px solid var(--accent-pink)', color: 'var(--accent-pink)' }}
                >
                  Cancel
                </button>
              )}
            </div>
            <form onSubmit={handleStudentLoanSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label">Loan Name</label>
                <input 
                  type="text" 
                  placeholder="e.g., Direct Subsidized Loan 01" 
                  className="form-input" 
                  value={loanForm.name} 
                  onChange={e => setLoanForm({...loanForm, name: e.target.value})} 
                  required 
                />
              </div>
              <div className="form-group">
                <label className="form-label">Type</label>
                <select 
                  className="form-select" 
                  value={loanForm.type} 
                  onChange={e => setLoanForm({...loanForm, type: e.target.value})}
                >
                  <option value="subsidized">Subsidized</option>
                  <option value="unsubsidized">Unsubsidized</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Principal Balance ($)</label>
                <input 
                  type="number" 
                  step="0.01" 
                  placeholder="0.00" 
                  className="form-input" 
                  value={loanForm.balance} 
                  onChange={e => setLoanForm({...loanForm, balance: e.target.value})} 
                  required 
                />
              </div>
              <div className="form-grid" style={{ marginBottom: 0 }}>
                <div className="form-group">
                  <label className="form-label">Interest Rate (%)</label>
                  <input 
                    type="number" 
                    step="0.01" 
                    placeholder="e.g. 4.5" 
                    className="form-input" 
                    value={loanForm.interest_rate} 
                    onChange={e => setLoanForm({...loanForm, interest_rate: e.target.value})} 
                    required 
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Accrued Interest ($)</label>
                  <input 
                    type="number" 
                    step="0.01" 
                    placeholder="0.00" 
                    className="form-input" 
                    value={loanForm.interest_accumulated} 
                    onChange={e => setLoanForm({...loanForm, interest_accumulated: e.target.value})} 
                    required 
                  />
                </div>
              </div>
              <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '0.2rem' }}>
                {editingLoanId ? "Save Changes" : "Register Loan"}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Filter controls */}
      <div className="glass-panel" style={{ padding: '0.75rem 1.5rem', marginBottom: '1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="form-label" style={{ margin: 0 }}>Account:</label>
            <select 
              className="form-select" 
              value={filterAccount} 
              onChange={e => setFilterAccount(e.target.value)}
              style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
            >
              <option value="">All Accounts</option>
              {financesData.accounts.map(acc => (
                <option key={acc.id} value={acc.id}>{acc.name}</option>
              ))}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <label className="form-label" style={{ margin: 0 }}>Range:</label>
            <select 
              className="form-select" 
              value={filterDateRange} 
              onChange={e => setFilterDateRange(e.target.value)}
              style={{ padding: '0.4rem 0.75rem', fontSize: '0.8rem' }}
            >
              <option value="all">All Time</option>
              <option value="this_month">This Month</option>
              <option value="last_30_days">Last 30 Days</option>
              <option value="last_90_days">Last 90 Days</option>
            </select>
          </div>
        </div>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
          DIAGNOSTICS: FOUND {financesData.transactions.length} LOGGED ITEMS
        </span>
      </div>

      {/* Main Cockpit grid (3 columns) */}
      <div className="grid-finances">
        
        {/* Column 1: Transaction History & Log Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="panel-header" style={{ borderBottom: '1px solid var(--border-cyan)' }}>
              <h3 className="panel-title">Transaction Ledger</h3>
            </div>
            <div className="panel-content" style={{ padding: '1.25rem', maxHeight: '400px', overflowY: 'auto', flex: 1 }}>
              {financesData.transactions.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '2rem 0' }}>No matching transactions.</p>
              ) : (
                <div className="item-list">
                  {financesData.transactions.map((tx) => (
                    <div key={tx.id} className="list-item" style={{ padding: '0.6rem 0.8rem' }}>
                      <div className="item-meta">
                        <span className="item-title" style={{ fontSize: '0.85rem' }}>{tx.merchant || "Unknown"}</span>
                        <span className="item-subtitle" style={{ fontSize: '0.7rem' }}>
                          {tx.date} • {tx.category}
                        </span>
                        <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.2rem', alignItems: 'center' }}>
                          <span className="badge tx-account-badge" style={{ fontSize: '0.55rem', padding: '0.05rem 0.3rem', background: 'rgba(0, 242, 254, 0.05)', borderColor: 'var(--border-cyan)' }}>
                            {tx.account_name?.toUpperCase() || 'UNASSIGNED'}
                          </span>
                          {tx.description && <span className="tx-desc-text" style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{tx.description}</span>}
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className={`badge badge-${tx.type}`} style={{ fontSize: '0.6rem', padding: '0.1rem 0.3rem' }}>
                          {tx.type.toUpperCase()}
                        </span>
                        <span className="item-value" style={{ fontSize: '0.9rem', color: tx.type === 'expense' ? 'var(--color-danger)' : tx.type === 'transfer' ? 'var(--accent-yellow)' : 'var(--color-success)' }}>
                          ${tx.amount.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Log Manual Transaction */}
          <div className="glass-panel">
            <div className="panel-header" style={{ borderBottom: '1px solid var(--border-cyan)' }}>
              <h3 className="panel-title">Log Manual Entry</h3>
            </div>
            <div className="panel-content" style={{ padding: '1.25rem' }}>
              <form onSubmit={(e) => {
                e.preventDefault();
                if (!txForm.account_id) {
                  showToast("Please select a target account.", "error");
                  return;
                }
                if (txForm.type === 'transfer' && !txForm.transfer_account_id) {
                  showToast("Please select a destination account for the transfer.", "error");
                  return;
                }
                handleFormSubmit(
                  'finances', 
                  { 
                    ...txForm, 
                    amount: parseFloat(txForm.amount),
                    account_id: parseInt(txForm.account_id),
                    transfer_account_id: txForm.type === 'transfer' ? parseInt(txForm.transfer_account_id) : undefined
                  }, 
                  setTxForm, 
                  { date: new Date().toISOString().split('T')[0], amount: '', type: 'expense', category: 'food', merchant: '', description: '', account_id: financesData.accounts[0]?.id || '', transfer_account_id: '' }
                );
              }} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div className="form-grid" style={{ marginBottom: 0 }}>
                  <div className="form-group">
                    <label className="form-label">Date</label>
                    <input type="date" className="form-input" value={txForm.date} onChange={e => setTxForm({...txForm, date: e.target.value})} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Amount ($)</label>
                    <input type="number" step="0.01" placeholder="0.00" className="form-input" value={txForm.amount} onChange={e => setTxForm({...txForm, amount: e.target.value})} required />
                  </div>
                </div>
                <div className="form-grid" style={{ marginBottom: 0 }}>
                  <div className="form-group">
                    <label className="form-label">Type</label>
                    <select className="form-select" value={txForm.type} onChange={e => setTxForm({...txForm, type: e.target.value})}>
                      <option value="expense">Expense</option>
                      <option value="income">Income</option>
                      <option value="transfer">Transfer</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Category</label>
                    <select className="form-select" value={txForm.category} onChange={e => setTxForm({...txForm, category: e.target.value})}>
                      <option value="food">Food & Groceries</option>
                      <option value="utilities">Utilities & Bills</option>
                      <option value="subscription">Subscriptions</option>
                      <option value="academic">Academic / Learning</option>
                      <option value="rent">Rent / Living</option>
                      <option value="salary">Salary / Earnings</option>
                      <option value="transfer">Transfer</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>
                <div className="form-grid" style={{ marginBottom: 0 }}>
                  <div className="form-group">
                    <label className="form-label">{txForm.type === 'transfer' ? 'From Account' : 'Account'}</label>
                    <select className="form-select" value={txForm.account_id} onChange={e => setTxForm({...txForm, account_id: e.target.value})} required>
                      <option value="">Select Account...</option>
                      {financesData.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                    </select>
                  </div>
                  {txForm.type === 'transfer' ? (
                    <div className="form-group">
                      <label className="form-label">To Account</label>
                      <select className="form-select" value={txForm.transfer_account_id} onChange={e => setTxForm({...txForm, transfer_account_id: e.target.value})} required>
                        <option value="">Select Account...</option>
                        {financesData.accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                      </select>
                    </div>
                  ) : (
                    <div className="form-group">
                      <label className="form-label">Merchant</label>
                      <input type="text" placeholder="e.g., Starbucks" className="form-input" value={txForm.merchant} onChange={e => setTxForm({...txForm, merchant: e.target.value})} required />
                    </div>
                  )}
                </div>
                <div className="form-group">
                  <label className="form-label">Description / Notes</label>
                  <input type="text" placeholder="Notes..." className="form-input" value={txForm.description} onChange={e => setTxForm({...txForm, description: e.target.value})} />
                </div>
                <button type="submit" className="btn-primary" style={{ width: '100%' }}>Log Transaction</button>
              </form>
            </div>
          </div>
        </div>

        {/* Column 2: Category Breakdown & Budgets */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header" style={{ borderBottom: '1px solid var(--border-cyan)' }}>
            <h3 className="panel-title">Budgets & Breakdown</h3>
          </div>
          <div className="panel-content" style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.5rem', flex: 1 }}>
            
            {/* Custom stacked telemetry bar chart */}
            {financesData.breakdown.length > 0 && (
              <div style={{ background: '#000000', border: '1px solid var(--border-cyan)', padding: '1rem', borderRadius: 'var(--border-radius)' }}>
                <span className="form-label" style={{ fontSize: '0.65rem', marginBottom: '0.5rem', display: 'block' }}>Relative Spending Telemetry</span>
                <div style={{ display: 'flex', height: '1.5rem', borderRadius: '4px', overflow: 'hidden', background: '#222' }}>
                  {financesData.breakdown.map((item, idx) => {
                    const totalExpense = financesData.breakdown.reduce((sum, b) => sum + b.total, 0);
                    const pct = totalExpense > 0 ? (item.total / totalExpense) * 100 : 0;
                    const colors = ['var(--accent-cyan)', 'var(--accent-pink)', 'var(--accent-purple)', '#eab308', 'var(--accent-green)', '#ff5722'];
                    return (
                      <div 
                        key={item.category} 
                        style={{ width: `${pct}%`, background: colors[idx % colors.length], height: '100%' }}
                        title={`${item.category}: $${item.total.toFixed(2)} (${pct.toFixed(1)}%)`}
                      />
                    );
                  })}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem 0.8rem', marginTop: '0.75rem' }}>
                  {financesData.breakdown.map((item, idx) => {
                    const colors = ['var(--accent-cyan)', 'var(--accent-pink)', 'var(--accent-purple)', '#eab308', 'var(--accent-green)', '#ff5722'];
                    return (
                      <div key={item.category} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.65rem' }}>
                        <span style={{ width: '8px', height: '8px', background: colors[idx % colors.length], borderRadius: '2px' }} />
                        <span style={{ color: 'var(--text-secondary)' }}>{item.category}: ${item.total.toFixed(0)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Budget Meters list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <span className="form-label" style={{ fontSize: '0.7rem', borderBottom: '1px dashed var(--border-cyan)', paddingBottom: '0.25rem' }}>Category Budget Meters</span>
              
              {financesData.breakdown.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '1rem 0' }}>No spending recorded for limits.</p>
              ) : (
                financesData.breakdown.map(item => {
                  const budget = financesData.budgets.find(b => b.category === item.category);
                  const limit = budget ? budget.limit_amount : 0;
                  const pct = limit > 0 ? (item.total / limit) * 100 : 0;
                  const isOver = limit > 0 && item.total > limit;
                  
                  return (
                    <div key={item.category} style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: 600 }}>
                        <span style={{ color: 'var(--text-primary)', textTransform: 'capitalize' }}>{item.category}</span>
                        <span style={{ color: isOver ? 'var(--accent-pink)' : 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                          ${item.total.toFixed(2)} {limit > 0 ? `/ $${limit.toFixed(0)}` : '(No limit)'}
                        </span>
                      </div>
                      <div style={{ height: '0.5rem', background: '#000000', border: '1px solid var(--border-cyan)', borderRadius: '2px', overflow: 'hidden', position: 'relative' }}>
                        {limit > 0 ? (
                          <div 
                            style={{ 
                              width: `${Math.min(pct, 100)}%`, 
                              height: '100%', 
                              background: isOver ? 'var(--accent-pink)' : 'var(--accent-cyan)',
                              boxShadow: isOver ? '0 0 10px rgba(255, 0, 127, 0.5)' : 'none',
                              animation: isOver ? 'pulse 1.5s infinite' : 'none'
                            }} 
                          />
                        ) : (
                          <div style={{ width: '100%', height: '100%', background: '#222' }} />
                        )}
                      </div>
                      {limit > 0 && (
                        <div className="budget-meta-row" style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: isOver ? 'var(--accent-pink)' : 'var(--text-muted)' }}>
                          <span>{pct.toFixed(0)}% Consumed</span>
                          <span>{isOver ? "⚠️ LIMIT EXCEEDED" : `$${(limit - item.total).toFixed(2)} Remaining`}</span>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Column 3: Recurring Payments Ledger */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header" style={{ borderBottom: '1px solid var(--border-cyan)' }}>
            <h3 className="panel-title">Recurring Payables</h3>
          </div>
          <div className="panel-content" style={{ padding: '1.25rem', flex: 1, display: 'flex', flexDirection: 'column' }}>
            {financesData.recurring.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', padding: '4rem 0' }}>
                <span className="material-symbols-outlined" style={{ fontSize: '32px', marginBottom: '0.5rem' }}>credit_card_off</span>
                <p style={{ fontSize: '0.85rem' }}>No recurring items logged.</p>
                <button className="btn-secondary" style={{ marginTop: '0.75rem', fontSize: '0.65rem' }} onClick={() => setShowManagePanel(true)}>Configure templates</button>
              </div>
            ) : (
              <div className="item-list">
                {financesData.recurring.map(rec => {
                  const nextDue = new Date(rec.next_due_date);
                  const isOverdue = nextDue < new Date();
                  
                  return (
                    <div key={rec.id} className="list-item" style={{ padding: '0.6rem 0.8rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'stretch' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-primary)' }}>{rec.name}</span>
                          <span className="recurring-details" style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                            Category: {rec.category} • Interval: {rec.interval}
                          </span>
                        </div>
                        <span style={{ fontSize: '1rem', fontWeight: 'bold', color: 'var(--accent-pink)' }}>
                          ${rec.amount.toFixed(2)}
                        </span>
                      </div>
                      
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px dashed #222', paddingTop: '0.5rem', marginTop: '0.2rem' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem' }}>
                          <span className="recurring-debit-info" style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Debits: {rec.account_name || 'Capital One Checking'}</span>
                          <span style={{ fontSize: '0.7rem', color: isOverdue ? 'var(--accent-pink)' : 'var(--accent-cyan)', fontWeight: 600 }}>
                            📅 Due: {rec.next_due_date} {isOverdue && "(OVERDUE)"}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button 
                            className="btn-danger-icon" 
                            onClick={() => deleteRecurring(rec.id)}
                            style={{ padding: '0.25rem 0.4rem', fontSize: '0.8rem', borderRadius: '4px' }}
                            title="Delete recurring template"
                          >
                            ×
                          </button>
                          <button 
                            className="btn-primary" 
                            onClick={() => payRecurring(rec.id)}
                            style={{ fontSize: '0.65rem', padding: '0.25rem 0.5rem', height: 'auto' }}
                          >
                            Mark Paid
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Column 4: Student Loans Tracker */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header" style={{ borderBottom: '1px solid var(--border-cyan)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 className="panel-title">Student Loans</h3>
          </div>
          <div className="panel-content" style={{ padding: '1.25rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            
            {/* Aggregates Summary */}
            {(() => {
              const loans = financesData.student_loans || [];
              const totalPrincipal = loans.reduce((sum, l) => sum + l.balance, 0);
              const totalInterest = loans.reduce((sum, l) => sum + l.interest_accumulated, 0);
              const totalLiability = totalPrincipal + totalInterest;
              
              return (
                <>
                  <div style={{ background: '#000000', border: '1px solid var(--border-cyan)', padding: '1rem', borderRadius: 'var(--border-radius)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>AGGREGATED LIABILITY (EXCLUDED FROM NET WEALTH)</span>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: '0.2rem' }}>
                      <span style={{ fontSize: '1.4rem', fontWeight: 'bold', color: 'var(--accent-pink)', fontFamily: 'var(--font-mono)' }}>
                        ${totalLiability.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Total Liability</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px dashed #222', paddingTop: '0.4rem', marginTop: '0.2rem', fontSize: '0.7rem' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Principal: <strong style={{ color: 'var(--text-primary)' }}>${totalPrincipal.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span>
                      <span style={{ color: 'var(--text-muted)' }}>Interest: <strong style={{ color: 'var(--text-primary)' }}>${totalInterest.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span>
                    </div>
                  </div>

                  {loans.length === 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', padding: '2rem 0' }}>
                      <span className="material-symbols-outlined" style={{ fontSize: '32px', marginBottom: '0.5rem' }}>school</span>
                      <p style={{ fontSize: '0.85rem' }}>No student loans registered.</p>
                      <button className="btn-secondary" style={{ marginTop: '0.75rem', fontSize: '0.65rem' }} onClick={() => setShowManagePanel(true)}>Configure loans</button>
                    </div>
                  ) : (
                    <div className="item-list" style={{ overflowY: 'auto', maxHeight: '350px' }}>
                      {loans.map(loan => {
                        const loanTotal = loan.balance + loan.interest_accumulated;
                        return (
                          <div key={loan.id} className="list-item" style={{ padding: '0.6rem 0.8rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', border: '1px solid rgba(255, 0, 127, 0.15)', borderRadius: '4px', marginBottom: '0.5rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontSize: '0.85rem', fontWeight: 'bold' }}>{loan.name}</span>
                              <span style={{ fontSize: '0.65rem', background: loan.type === 'subsidized' ? 'var(--accent-cyan)' : 'var(--accent-pink)', color: '#000000', padding: '0.1rem 0.3rem', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>
                                {loan.type.toUpperCase()}
                              </span>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                              <span style={{ color: 'var(--text-secondary)' }}>Interest Rate: {loan.interest_rate}%</span>
                              <span style={{ fontWeight: 'bold', color: 'var(--text-primary)' }}>
                                Total: ${loanTotal.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                              </span>
                            </div>
                            {showManagePanel && (
                              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', borderTop: '1px dashed #222', paddingTop: '0.4rem', marginTop: '0.2rem' }}>
                                <button
                                  className="btn-danger-icon"
                                  onClick={() => deleteStudentLoan(loan.id, loan.name)}
                                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.65rem', borderRadius: '2px' }}
                                  title="Delete loan"
                                >
                                  Delete
                                </button>
                                <button
                                  className="btn-primary"
                                  onClick={() => {
                                    setEditingLoanId(loan.id);
                                    setLoanForm({
                                      name: loan.name,
                                      type: loan.type,
                                      balance: String(loan.balance),
                                      interest_rate: String(loan.interest_rate),
                                      interest_accumulated: String(loan.interest_accumulated)
                                    });
                                    setShowManagePanel(true);
                                  }}
                                  style={{ padding: '0.2rem 0.5rem', fontSize: '0.65rem', height: 'auto' }}
                                >
                                  Edit
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        </div>
      </div>
      {renderRelatedAreas("Finances")}
    </div>
  );
}

export default FinancesTab;
