import React, { useState, useEffect } from 'react';
import { activateOnKey } from '../a11y';

const API_BASE = import.meta.env.VITE_API_URL || (
  window.location.port === '5174'
    ? `http://${window.location.hostname}:8001/api`
    : window.location.port === '5173'
      ? `http://${window.location.hostname}:8000/api`
      : `${window.location.origin}/api`
);

function CareerTab({ careerData, handleFormSubmit, renderRelatedAreas, showToast }) {
  const [localData, setLocalData] = useState(careerData || { applications: [], leads: [], profiles: [], stats: {} });
  const [activeSubTab, setActiveSubTab] = useState('leads'); // 'leads', 'outreach', 'profiles', 'tracker'
  
  // URL Ingest state
  const [pastedUrl, setPastedUrl] = useState('');
  const [ingestProfileId, setIngestProfileId] = useState('');
  const [ingesting, setIngesting] = useState(false);
  
  // Profile creation state
  const [profileForm, setProfileForm] = useState({
    name: '',
    resume_path: '',
    keywords: '',
    locations: '',
    active: 1
  });
  
  // Scraping state
  const [scraping, setScraping] = useState(false);
  
  // Detail selection states
  const [selectedLead, setSelectedLead] = useState(null);
  const [selectedApp, setSelectedApp] = useState(null);
  const [processingLeadId, setProcessingLeadId] = useState(null);
  const [sendingEmailId, setSendingEmailId] = useState(null);
  
  // Local edit states for outreach station
  const [editRecruiterName, setEditRecruiterName] = useState('');
  const [editRecruiterEmail, setEditRecruiterEmail] = useState('');
  const [editColdEmail, setEditColdEmail] = useState('');
  const [editBullets, setEditBullets] = useState('');
  const [editCoverLetter, setEditCoverLetter] = useState('');
  const [isSavingAppEdits, setIsSavingAppEdits] = useState(false);

  // Sync props to local state
  useEffect(() => {
    if (careerData) {
      setLocalData(careerData);
      if (careerData.profiles && careerData.profiles.length > 0 && !ingestProfileId) {
        setIngestProfileId(String(careerData.profiles[0].id));
      }
    }
  }, [careerData]);

  const refreshData = async () => {
    try {
      const res = await fetch(`${API_BASE}/career`).then(r => r.json());
      setLocalData(res);
      if (res.profiles && res.profiles.length > 0 && !ingestProfileId) {
        setIngestProfileId(String(res.profiles[0].id));
      }
    } catch (err) {
      console.error("Error fetching career data locally:", err);
    }
  };

  const handleIngestUrl = async (e) => {
    e.preventDefault();
    if (!pastedUrl || !ingestProfileId) return;
    setIngesting(true);
    try {
      const res = await fetch(`${API_BASE}/career/leads/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: pastedUrl, profile_id: parseInt(ingestProfileId) })
      }).then(r => r.json());
      
      if (res.status === 'success') {
        setPastedUrl('');
        showToast(`Added lead: ${res.title} at ${res.company}`, "success");
        await refreshData();
      } else {
        showToast("Couldn't add that link. " + (res.detail || "Check the URL and try again."), "error");
      }
    } catch {
      showToast("Couldn't add that link. Check your connection and try again.", "error");
    } finally {
      setIngesting(false);
    }
  };

  const handleIgnoreLead = async (leadId) => {
    if (!confirm("Ignore this lead? It will leave your queue.")) return;
    try {
      const res = await fetch(`${API_BASE}/career/leads/${leadId}/ignore`, { method: 'POST' }).then(r => r.json());
      if (res.status === 'success') {
        setSelectedLead(null);
        await refreshData();
      }
    } catch {
      showToast("Couldn't ignore that lead. Try again.", "error");
    }
  };

  const handleProcessLead = async (leadId) => {
    setProcessingLeadId(leadId);
    try {
      const res = await fetch(`${API_BASE}/career/leads/${leadId}/approve`, { method: 'POST' }).then(r => r.json());
      if (res.status === 'success') {
        showToast("Application tailored. The cover letter and outreach draft are ready under Outreach.", "success");
        setSelectedLead(null);
        setActiveSubTab('outreach');
        await refreshData();
        
        const newApp = res.application_id;
        const freshData = await fetch(`${API_BASE}/career`).then(r => r.json());
        const matched = freshData.applications.find(a => a.id === newApp);
        if (matched) {
          handleSelectApp(matched);
        }
      } else {
        showToast("Tailoring failed. " + (res.detail || "Try again."), "error");
      }
    } catch {
      showToast("Tailoring failed. Try again.", "error");
    } finally {
      setProcessingLeadId(null);
    }
  };

  const handleSelectApp = (app) => {
    setSelectedApp(app);
    setEditRecruiterName(app.recruiter_name || 'Hiring Team');
    setEditRecruiterEmail(app.recruiter_email || '');
    setEditColdEmail(app.cold_email_draft || '');
    setEditBullets(app.tailored_bullets || '');
    setEditCoverLetter(app.cover_letter || '');
  };

  const handleSaveAppEdits = async () => {
    if (!selectedApp) return;
    setIsSavingAppEdits(true);
    try {
      const res = await fetch(`${API_BASE}/career/applications/${selectedApp.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recruiter_name: editRecruiterName,
          recruiter_email: editRecruiterEmail,
          cold_email_draft: editColdEmail,
          tailored_bullets: editBullets,
          cover_letter: editCoverLetter
        })
      }).then(r => r.json());
      
      if (res.status === 'success') {
        showToast("Edits saved.", "success");
        await refreshData();
        const updatedApp = {
          ...selectedApp,
          recruiter_name: editRecruiterName,
          recruiter_email: editRecruiterEmail,
          cold_email_draft: editColdEmail,
          tailored_bullets: editBullets,
          cover_letter: editCoverLetter
        };
        setSelectedApp(updatedApp);
      } else {
        showToast("Couldn't save edits. " + (res.detail || "Try again."), "error");
      }
    } catch {
      showToast("Couldn't save edits. Try again.", "error");
    } finally {
      setIsSavingAppEdits(false);
    }
  };

  const handleSendEmail = async (appId) => {
    if (!confirm("Send this outreach email now?")) return;
    setSendingEmailId(appId);
    try {
      const res = await fetch(`${API_BASE}/career/applications/${appId}/send-email`, { method: 'POST' }).then(r => r.json());
      if (res.status === 'success') {
        showToast(res.message, "success");
        await refreshData();
        if (selectedApp && selectedApp.id === appId) {
          setSelectedApp(prev => ({ ...prev, outreach_status: 'sent' }));
        }
      } else {
        showToast("Couldn't send the email. " + (res.detail || "Try again."), "error");
      }
    } catch {
      showToast("Couldn't send the email. Try again.", "error");
    } finally {
      setSendingEmailId(null);
    }
  };

  const handleTriggerScrape = async () => {
    setScraping(true);
    try {
      const res = await fetch(`${API_BASE}/career/scrape`, { method: 'POST' }).then(r => r.json());
      if (res.status === 'started') {
        showToast("Discovery started. New leads will appear shortly.", "success");
      }
    } catch {
      showToast("Couldn't start discovery. Try again.", "error");
    } finally {
      setScraping(false);
    }
  };

  const handleAddProfile = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/career/profiles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileForm)
      }).then(r => r.json());
      
      if (res.status === 'success') {
        setProfileForm({ name: '', resume_path: '', keywords: '', locations: '', active: 1 });
        showToast("Search profile added.", "success");
        await refreshData();
      }
    } catch {
      showToast("Couldn't add the profile. Try again.", "error");
    }
  };

  const handleDeleteProfile = async (id) => {
    if (!confirm("Delete this search profile? This can't be undone.")) return;
    try {
      const res = await fetch(`${API_BASE}/career/profiles/${id}`, { method: 'DELETE' }).then(r => r.json());
      if (res.status === 'success') {
        await refreshData();
      }
    } catch {
      showToast("Couldn't delete the profile. Try again.", "error");
    }
  };

  const copyToClipboard = (text, message = "Copied to clipboard!") => {
    navigator.clipboard.writeText(text);
    showToast(message, "success");
  };

  const stats = localData.stats || {};

  return (
    <div>
      <header className="page-header page-header--compact">
        <h1 className="page-title">Career</h1>
        <div className="page-header-meta">
          <p className="page-subtitle">Priority 1: Income</p>
          <button 
            onClick={handleTriggerScrape} 
            disabled={scraping} 
            className="btn-primary" 
            style={{ fontSize: 'var(--text-sm)', padding: '0.5rem 1rem', border: '1px solid var(--accent-cyan)', background: 'var(--surface-2)', color: 'var(--accent-cyan)' }}
          >
            {scraping ? "Running discovery…" : "Run discovery"}
          </button>
        </div>
      </header>

      {/* Metrics Banner */}
      <div className="grid-4col" style={{ marginBottom: '1.25rem', gap: '0.75rem' }}>
        <div className="glass-panel" style={{ padding: '0.75rem', }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'inherit' }}>Leads found</span>
          <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--accent-cyan)', fontSize: 'var(--text-lg)' }}>{localData.leads?.length || 0}</h3>
        </div>
        <div className="glass-panel" style={{ padding: '0.75rem', }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'inherit' }}>US remote</span>
          <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--accent-green)', fontSize: 'var(--text-lg)' }}>{stats.tier1_count || 0}</h3>
        </div>
        <div className="glass-panel" style={{ padding: '0.75rem', }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'inherit' }}>New England</span>
          <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--accent-yellow)', fontSize: 'var(--text-lg)' }}>{stats.tier2_count || 0}</h3>
        </div>
        <div className="glass-panel" style={{ padding: '0.75rem', }}>
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'inherit' }}>Tailored applications</span>
          <h3 style={{ margin: '0.2rem 0 0 0', color: 'var(--text-secondary)', fontSize: 'var(--text-lg)' }}>{localData.applications?.length || 0}</h3>
        </div>
      </div>

      {/* Sub-Navigation Tabs */}
      <div className="tab-navigation" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
        <button 
          className={`tab-btn ${activeSubTab === 'leads' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('leads')}
          style={{ padding: '0.5rem 1rem', background: activeSubTab === 'leads' ? 'var(--surface-2)' : 'transparent', border: 'none', borderBottom: activeSubTab === 'leads' ? '2px solid var(--accent-cyan)' : 'none', color: activeSubTab === 'leads' ? 'var(--accent-cyan)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          Ready to apply ({localData.leads?.length || 0})
        </button>
        <button 
          className={`tab-btn ${activeSubTab === 'outreach' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('outreach')}
          style={{ padding: '0.5rem 1rem', background: activeSubTab === 'outreach' ? 'var(--surface-2)' : 'transparent', border: 'none', borderBottom: activeSubTab === 'outreach' ? '2px solid var(--text-secondary)' : 'none', color: activeSubTab === 'outreach' ? 'var(--text-secondary)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          Outreach ({localData.applications?.length || 0})
        </button>
        <button 
          className={`tab-btn ${activeSubTab === 'profiles' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('profiles')}
          style={{ padding: '0.5rem 1rem', background: activeSubTab === 'profiles' ? 'color-mix(in srgb, var(--color-warning) 10%, transparent)' : 'transparent', border: 'none', borderBottom: activeSubTab === 'profiles' ? '2px solid var(--accent-yellow)' : 'none', color: activeSubTab === 'profiles' ? 'var(--accent-yellow)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          Search profiles
        </button>
        <button 
          className={`tab-btn ${activeSubTab === 'tracker' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('tracker')}
          style={{ padding: '0.5rem 1rem', background: activeSubTab === 'tracker' ? 'color-mix(in srgb, var(--color-success) 10%, transparent)' : 'transparent', border: 'none', borderBottom: activeSubTab === 'tracker' ? '2px solid var(--accent-green)' : 'none', color: activeSubTab === 'tracker' ? 'var(--accent-green)' : 'var(--text-muted)', cursor: 'pointer' }}
        >
          Applications
        </button>
      </div>

      {/* SUBTAB 1: JOB LEADS QUEUE */}
      {activeSubTab === 'leads' && (
        <div className="grid-2col">
          {/* Left Column: Leads list */}
          <div className="glass-panel">
            <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 className="panel-title">Target Job Opportunities</h3>
              <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', fontFamily: 'inherit' }}>Sorted by match score</span>
            </div>
            
            <div className="panel-content">
              {(!localData.leads || localData.leads.length === 0) ? (
                <p style={{ color: 'var(--text-muted)', }}>No active job leads in queue. Click 'Run discovery' above to ingest fresh positions.</p>
              ) : (
                <div className="item-list" style={{ maxHeight: '550px', overflowY: 'auto' }}>
                  {localData.leads.map((lead) => (
                    <div role="button" tabIndex={0} onKeyDown={activateOnKey} 
                      key={lead.id} 
                      className={`list-item ${selectedLead?.id === lead.id ? 'active' : ''}`}
                      onClick={() => setSelectedLead(lead)}
                      style={{ cursor: 'pointer', padding: '0.75rem', borderRadius: '4px', background: selectedLead?.id === lead.id ? 'var(--surface-2)' : undefined, marginBottom: '0.5rem' }}
                    >
                      <div className="item-meta">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <span className="item-title" style={{ fontWeight: 'bold', fontSize: 'var(--text-sm)' }}>{lead.role}</span>
                          <span style={{ 
                            fontSize: 'var(--text-xs)', 
                            padding: '0.15rem 0.4rem', 
                            borderRadius: '3px', 
                            fontWeight: 'bold',
                            background: (lead.match_score || 70) >= 80 ? 'color-mix(in srgb, var(--color-success) 15%, transparent)' : 'color-mix(in srgb, var(--color-warning) 15%, transparent)',
                            color: (lead.match_score || 70) >= 80 ? 'var(--accent-green)' : 'var(--accent-yellow)',
                            border: (lead.match_score || 70) >= 80 ? '1px solid var(--accent-green)' : '1px solid var(--accent-yellow)'
                          }}>
                            Match: {lead.match_score || 75}%
                          </span>
                        </div>
                        <span className="item-subtitle" style={{ fontSize: 'var(--text-sm)' }}>{lead.company} • <span style={{ fontStyle: 'italic' }}>{lead.location}</span></span>
                        
                        <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.35rem', flexWrap: 'wrap', alignItems: 'center' }}>
                          {lead.is_remote ? (
                            <span style={{ fontSize: 'var(--text-xs)', padding: '0.1rem 0.3rem', background: 'var(--surface-2)', color: 'var(--accent-cyan)', borderRadius: '3px', border: '1px solid var(--accent-cyan)' }}>
                              US remote
                            </span>
                          ) : (
                            <span style={{ fontSize: 'var(--text-xs)', padding: '0.1rem 0.3rem', background: 'var(--surface-2)', color: 'var(--text-secondary)', borderRadius: '3px', border: '1px solid var(--text-secondary)' }}>
                              New England regional
                            </span>
                          )}
                          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                            Source: {lead.source.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Lead details & Ingest panel */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Lead Details display */}
            {selectedLead ? (
              <div className="glass-panel">
                <div className="panel-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h3 className="panel-title">{selectedLead.role}</h3>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>{selectedLead.company}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button 
                      onClick={() => handleIgnoreLead(selectedLead.id)} 
                      className="btn-danger" 
                      style={{ padding: '0.3rem 0.6rem', fontSize: 'var(--text-xs)' }}
                    >
                      Ignore
                    </button>
                    <button 
                      onClick={() => handleProcessLead(selectedLead.id)} 
                      disabled={processingLeadId !== null}
                      className="btn-primary" 
                      style={{ padding: '0.3rem 0.75rem', fontSize: 'var(--text-xs)', fontWeight: 'bold' }}
                    >
                      {processingLeadId === selectedLead.id ? "Tailoring…" : "Approve and tailor"}
                    </button>
                  </div>
                </div>
                <div className="panel-content" style={{ maxHeight: '350px', overflowY: 'auto' }}>
                  <p style={{ fontSize: 'var(--text-sm)', marginBottom: '0.5rem' }}>
                    <strong>Location:</strong> {selectedLead.location} | <strong>Classification:</strong> {selectedLead.is_remote ? 'Tier 1 US Remote' : 'Tier 2 New England Regional'}
                  </p>
                  <p style={{ fontSize: 'var(--text-xs)', color: 'var(--accent-cyan)' }}>
                    <a href={selectedLead.job_url} target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>View listing on portal</a>
                  </p>
                  <hr style={{ border: 'none', borderBottom: '1px solid var(--border-glass)', margin: '0.75rem 0' }} />
                  <p style={{ fontWeight: 'bold', fontSize: 'var(--text-sm)', marginBottom: '0.25rem' }}>Job Description:</p>
                  <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                    {selectedLead.job_description}
                  </pre>
                </div>
              </div>
            ) : (
              <div className="glass-panel" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '150px' }}>
                <p style={{ color: 'var(--text-muted)' }}>Select a job lead from the queue to view details and generate a tailored application packet.</p>
              </div>
            )}

            {/* Paste URL for Ingestion */}
            <div className="glass-panel">
              <div className="panel-header">
                <h3 className="panel-title">Direct URL Ingest</h3>
              </div>
              <div className="panel-content">
                <form onSubmit={handleIngestUrl}>
                  <div className="form-group" style={{ marginBottom: '1rem' }}>
                    <label className="form-label">Job Posting URL</label>
                    <input 
                      type="url" 
                      placeholder="https://www.linkedin.com/jobs/view/..." 
                      className="form-input" 
                      value={pastedUrl} 
                      onChange={e => setPastedUrl(e.target.value)} 
                      required 
                    />
                  </div>
                  
                  <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                    <label className="form-label">Search Track Target</label>
                    <select 
                      className="form-select" 
                      value={ingestProfileId} 
                      onChange={e => setIngestProfileId(e.target.value)} 
                      required
                    >
                      {localData.profiles?.map(p => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                    </select>
                  </div>
                  
                  <button type="submit" className="btn-primary" style={{ width: '100%' }} disabled={ingesting}>
                    {ingesting ? "Ingesting..." : "Ingest Listing"}
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 2: OUTREACH & TAILORING STATION */}
      {activeSubTab === 'outreach' && (
        <div className="grid-2col">
          {/* Left Column: Applications list with outreach pending */}
          <div className="glass-panel">
            <div className="panel-header">
              <h3 className="panel-title">Outreach Station & Staged Packets</h3>
            </div>
            <div className="panel-content">
              {(!localData.applications || localData.applications.length === 0) ? (
                <p style={{ color: 'var(--text-muted)' }}>No tailored outreach templates found. Click 'APPROVE & TAILOR' on a lead in the queue first.</p>
              ) : (
                <div className="item-list">
                  {localData.applications.map((app) => (
                    <div role="button" tabIndex={0} onKeyDown={activateOnKey} 
                      key={app.id} 
                      className={`list-item ${selectedApp?.id === app.id ? 'active' : ''}`}
                      onClick={() => handleSelectApp(app)}
                      style={{ cursor: 'pointer', padding: '0.75rem', borderRadius: '4px', background: selectedApp?.id === app.id ? 'var(--surface-2)' : undefined, marginBottom: '0.5rem' }}
                    >
                      <div className="item-meta" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                        <div>
                          <span className="item-title" style={{ fontWeight: 'bold' }}>{app.role}</span>
                          <span className="item-subtitle">{app.company}</span>
                          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', display: 'block', marginTop: '0.2rem' }}>
                            Recruiter: {app.recruiter_name || 'Hiring Team'} ({app.recruiter_email || 'No email'})
                          </span>
                        </div>
                        <span className={`badge badge-${app.outreach_status || 'pending'}`}>
                          Outreach: {app.outreach_status || 'pending'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Tailoring Review & Email Sender */}
          <div className="glass-panel" style={{ width: '100%' }}>
            {selectedApp ? (
              <div className="panel-content" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-glass)', paddingBottom: '0.5rem' }}>
                  <div>
                    <h3 className="panel-title" style={{ color: 'var(--text-secondary)' }}>{selectedApp.role} @ {selectedApp.company}</h3>
                    <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>Dual-Anchor Application Packet</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button 
                      onClick={handleSaveAppEdits} 
                      disabled={isSavingAppEdits}
                      className="btn-secondary" 
                      style={{ fontSize: 'var(--text-xs)', padding: '0.2rem 0.5rem' }}
                    >
                      {isSavingAppEdits ? "Saving..." : "Save Edits"}
                    </button>
                    <button 
                      onClick={() => handleSendEmail(selectedApp.id)} 
                      disabled={sendingEmailId === selectedApp.id || selectedApp.outreach_status === 'sent'}
                      className="btn-primary" 
                      style={{ background: selectedApp.outreach_status === 'sent' ? 'var(--bg-surface)' : 'var(--text-primary)', color: selectedApp.outreach_status === 'sent' ? 'var(--text-muted)' : 'var(--bg-primary, #ffffff) !important', border: selectedApp.outreach_status === 'sent' ? '1px solid var(--border-cyan)' : 'none', fontSize: 'var(--text-xs)', padding: '0.2rem 0.5rem', fontWeight: 'bold' }}
                    >
                      {sendingEmailId === selectedApp.id ? "Sending..." : selectedApp.outreach_status === 'sent' ? "Outreach Logged" : "Send outreach email"}
                    </button>
                  </div>
                </div>

                {/* Recruiter Details Form */}
                <div className="form-grid">
                  <div className="form-group">
                    <label className="form-label">Recruiter / Manager Name</label>
                    <input 
                      type="text" 
                      className="form-input" 
                      value={editRecruiterName} 
                      onChange={e => setEditRecruiterName(e.target.value)} 
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Recruiter Email Address</label>
                    <input 
                      type="email" 
                      className="form-input" 
                      value={editRecruiterEmail} 
                      onChange={e => setEditRecruiterEmail(e.target.value)} 
                    />
                  </div>
                </div>

                {/* Cold Outreach Email Editor */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label className="form-label">Recruiter Cold Email (With Calendar Slots)</label>
                    <button 
                      className="link-btn" 
                      onClick={() => copyToClipboard(editColdEmail, "Email draft copied!")} 
                      style={{ fontSize: 'var(--text-xs)', background: 'transparent', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', textDecoration: 'underline' }}
                    >
                      Copy Draft
                    </button>
                  </div>
                  <textarea 
                    rows={6} 
                    className="form-input" 
                    style={{ resize: 'vertical', width: '100%', padding: '0.5rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-glass)', color: 'inherit', fontFamily: 'inherit', fontSize: 'var(--text-sm)' }}
                    value={editColdEmail} 
                    onChange={e => setEditColdEmail(e.target.value)} 
                  />
                </div>

                {/* Tailored Bullets Editor */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label className="form-label">Dual-Anchor Resume Bullets (7Y Experience + CS/AI Degree)</label>
                    <button 
                      className="link-btn" 
                      onClick={() => copyToClipboard(editBullets, "Tailored bullets copied!")} 
                      style={{ fontSize: 'var(--text-xs)', background: 'transparent', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', textDecoration: 'underline' }}
                    >
                      Copy Bullets
                    </button>
                  </div>
                  <textarea 
                    rows={4} 
                    className="form-input" 
                    style={{ resize: 'vertical', width: '100%', padding: '0.5rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-glass)', color: 'inherit', fontFamily: 'inherit', fontSize: 'var(--text-sm)' }}
                    value={editBullets} 
                    onChange={e => setEditBullets(e.target.value)} 
                  />
                </div>

                {/* Tailored Cover Letter Editor */}
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <label className="form-label">Tailored Cover Letter</label>
                    <button 
                      className="link-btn" 
                      onClick={() => copyToClipboard(editCoverLetter, "Cover letter copied!")} 
                      style={{ fontSize: 'var(--text-xs)', background: 'transparent', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', textDecoration: 'underline' }}
                    >
                      Copy Cover Letter
                    </button>
                  </div>
                  <textarea 
                    rows={6} 
                    className="form-input" 
                    style={{ resize: 'vertical', width: '100%', padding: '0.5rem', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-glass)', color: 'inherit', fontFamily: 'inherit', fontSize: 'var(--text-sm)' }}
                    value={editCoverLetter} 
                    onChange={e => setEditCoverLetter(e.target.value)} 
                  />
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', height: '100%', justifyContent: 'center', alignItems: 'center', minHeight: '300px', color: 'var(--text-muted)' }}>
                Select a tailored application in the outreach list to review materials.
              </div>
            )}
          </div>
        </div>
      )}

      {/* SUBTAB 3: SEARCH PROFILES */}
      {activeSubTab === 'profiles' && (
        <div className="grid-2col">
          {/* Left Column: Manage Profiles list */}
          <div className="glass-panel">
            <div className="panel-header">
              <h3 className="panel-title">Active Job Search Tracks</h3>
            </div>
            <div className="panel-content">
              {(!localData.profiles || localData.profiles.length === 0) ? (
                <p style={{ color: 'var(--text-muted)' }}>No search profiles defined yet. Add one below.</p>
              ) : (
                <div className="item-list">
                  {localData.profiles.map(p => (
                    <div key={p.id} className="list-item" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem', border: '1px solid var(--border-glass)', borderRadius: '4px', marginBottom: '0.5rem' }}>
                      <div className="item-meta">
                        <span className="item-title" style={{ fontWeight: 'bold' }}>{p.name}</span>
                        <span className="item-subtitle" style={{ fontSize: 'var(--text-xs)' }}>Keywords: {p.keywords}</span>
                        <span className="item-subtitle" style={{ fontSize: 'var(--text-xs)' }}>Locations: {p.locations}</span>
                        {p.resume_path && <span className="item-subtitle" style={{ fontSize: 'var(--text-xs)', fontFamily: 'inherit', color: 'var(--text-secondary)' }}>Resume: {p.resume_path.split('/').pop()}</span>}
                      </div>
                      <button 
                        onClick={() => handleDeleteProfile(p.id)} 
                        className="btn-primary" 
                        style={{ background: 'color-mix(in srgb, var(--color-danger) 10%, transparent)', color: 'var(--color-danger)', border: 'none', padding: '0.2rem 0.5rem', fontSize: 'var(--text-xs)' }}
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Add Profile form */}
          <div className="glass-panel">
            <div className="panel-header">
              <h3 className="panel-title">Add Search Profile</h3>
            </div>
            <div className="panel-content">
              <form onSubmit={handleAddProfile}>
                <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                  <label className="form-label">Profile Track Name</label>
                  <input 
                    type="text" 
                    placeholder="e.g. AI Agent & Software Engineering" 
                    className="form-input" 
                    value={profileForm.name} 
                    onChange={e => setProfileForm({ ...profileForm, name: e.target.value })} 
                    required 
                  />
                </div>
                
                <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                  <label className="form-label">Master Resume File Path (Optional)</label>
                  <input 
                    type="text" 
                    placeholder="./storage/sample_resume.html" 
                    className="form-input" 
                    value={profileForm.resume_path} 
                    onChange={e => setProfileForm({ ...profileForm, resume_path: e.target.value })} 
                  />
                </div>
                
                <div className="form-group" style={{ marginBottom: '0.75rem' }}>
                  <label className="form-label">Search Keywords (Comma-separated)</label>
                  <input 
                    type="text" 
                    placeholder="AI Agent, Software Engineer, Machine Learning, Python" 
                    className="form-input" 
                    value={profileForm.keywords} 
                    onChange={e => setProfileForm({ ...profileForm, keywords: e.target.value })} 
                    required 
                  />
                </div>
                
                <div className="form-group" style={{ marginBottom: '1.25rem' }}>
                  <label className="form-label">Target Locations (Comma-separated)</label>
                  <input 
                    type="text" 
                    placeholder="Remote, Boston MA, Massachusetts" 
                    className="form-input" 
                    value={profileForm.locations} 
                    onChange={e => setProfileForm({ ...profileForm, locations: e.target.value })} 
                    required 
                  />
                </div>
                
                <button type="submit" className="btn-primary" style={{ width: '100%' }}>Create Profile Track</button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* SUBTAB 4: LOGGED APPLICATIONS LIST */}
      {activeSubTab === 'tracker' && (
        <div className="grid-2col">
          {/* Left Column: Job Applications list */}
          <div className="glass-panel">
            <div className="panel-header">
              <h3 className="panel-title">Active Applications Logs</h3>
            </div>
            <div className="panel-content">
              {(!localData.applications || localData.applications.length === 0) ? (
                <p style={{ color: 'var(--text-muted)' }}>No job applications logged yet.</p>
              ) : (
                <div className="item-list" style={{ maxHeight: '600px', overflowY: 'auto' }}>
                  {localData.applications.map((app) => (
                    <div key={app.id} className="list-item" style={{ padding: '0.75rem', border: '1px solid var(--border-glass)', borderRadius: '4px', marginBottom: '0.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div className="item-meta">
                        <span className="item-title" style={{ fontWeight: 'bold' }}>{app.role} at {app.company}</span>
                        <span className="item-subtitle" style={{ fontSize: 'var(--text-xs)' }}>
                          Applied: {app.date_applied} {app.salary_range ? `• Salary: ${app.salary_range}` : ''}
                        </span>
                        {app.notes && <span className="item-subtitle career-app-notes" style={{ fontStyle: 'italic', marginTop: '0.25rem', display: 'block' }}>"{app.notes}"</span>}
                        {app.job_description_url && (
                          <span className="career-app-link" style={{ fontSize: 'var(--text-xs)', marginTop: '0.25rem', display: 'block' }}>
                            <a href={app.job_description_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-cyan)', textDecoration: 'underline' }}>
                              Job Posting URL
                            </a>
                          </span>
                        )}
                      </div>
                      <span className={`badge badge-${app.status}`}>
                        {app.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Log new application manually */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="glass-panel">
              <div className="panel-header">
                <h3 className="panel-title">Log New Application (Manual)</h3>
              </div>
              <div className="panel-content">
                <form onSubmit={async (e) => {
                  e.preventDefault();
                  const form = e.target;
                  const payload = {
                    date_applied: form.date_applied.value,
                    company: form.company.value,
                    role: form.role.value,
                    salary_range: form.salary_range.value,
                    status: form.status.value,
                    job_description_url: form.job_description_url.value,
                    notes: form.notes.value
                  };
                  try {
                    await handleFormSubmit('career', payload, () => {}, {});
                    form.reset();
                    await refreshData();
                  } catch {
                    showToast("Couldn't log the application. Try again.", "error");
                  }
                }}>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Date Applied</label>
                      <input type="date" name="date_applied" className="form-input" defaultValue={new Date().toISOString().split('T')[0]} required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Status</label>
                      <select name="status" className="form-select" defaultValue="applied">
                        <option value="applied">Applied</option>
                        <option value="interviewing">Interviewing</option>
                        <option value="offered">Offered</option>
                        <option value="rejected">Rejected</option>
                        <option value="withdrawn">Withdrawn</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-grid">
                    <div className="form-group">
                      <label className="form-label">Company</label>
                      <input type="text" name="company" placeholder="e.g., Anthropic" className="form-input" required />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Role / Title</label>
                      <input type="text" name="role" placeholder="e.g., AI Agent Engineer" className="form-input" required />
                    </div>
                  </div>
                  <div className="form-group" style={{ marginBottom: '1rem' }}>
                    <label className="form-label">Salary Range / Package</label>
                    <input type="text" name="salary_range" placeholder="e.g., $110k - $140k" className="form-input" />
                  </div>
                  <div className="form-group" style={{ marginBottom: '1rem' }}>
                    <label className="form-label">Job Posting URL</label>
                    <input type="text" name="job_description_url" placeholder="https://..." className="form-input" />
                  </div>
                  <div className="form-group" style={{ marginBottom: '1.5rem' }}>
                    <label className="form-label">Notes & Details</label>
                    <input type="text" name="notes" placeholder="e.g., Direct application packet" className="form-input" />
                  </div>
                  <button type="submit" className="btn-primary" style={{ width: '100%' }}>Add Log Entry</button>
                </form>
              </div>
            </div>
            {renderRelatedAreas("Career")}
          </div>
        </div>
      )}
    </div>
  );
}

export default CareerTab;
