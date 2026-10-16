import { useState, useCallback } from 'react';
import { activateOnKey, useDialog } from '../a11y';
import { API_BASE } from '../api';

const STATUSES = [
  { id: 'applied', label: 'Applied' },
  { id: 'interviewing', label: 'Interviewing' },
  { id: 'offered', label: 'Offered' },
  { id: 'rejected', label: 'Rejected' },
  { id: 'withdrawn', label: 'Withdrawn' },
];
const STATUS_LABEL = Object.fromEntries(STATUSES.map(s => [s.id, s.label]));

const EVENT_KINDS = [
  { id: 'interview', label: 'Interview' },
  { id: 'recruiter_contact', label: 'Recruiter contact' },
  { id: 'offer', label: 'Offer' },
  { id: 'note', label: 'Note' },
];
const EVENT_LABEL = { status_change: 'Status change', ...Object.fromEntries(EVENT_KINDS.map(k => [k.id, k.label])) };

const APP_FIELDS = ['company', 'role', 'date_applied', 'salary_range', 'job_description_url', 'notes', 'recruiter_name', 'recruiter_email'];
const EMPTY_LEAD = { company: '', role: '', job_url: '', location: '', salary_range: '' };

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

const formatDate = (value) => {
  if (!value) return '';
  const [y, m, d] = value.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};

// fetch + JSON with the backend's {detail} error text surfaced
const request = async (path, method = 'GET', body) => {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed');
  return data;
};

function ApplicationCard({ app, onOpen, onDragStart, onDragEnd }) {
  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      className="career-card"
      onClick={() => onOpen(app.id)}
      onKeyDown={activateOnKey}
      onDragStart={e => { e.dataTransfer.setData('text/plain', String(app.id)); e.dataTransfer.effectAllowed = 'move'; onDragStart(app.id); }}
      onDragEnd={onDragEnd}
      aria-label={`${app.role} at ${app.company}, ${STATUS_LABEL[app.status] || app.status}. Open details`}
    >
      <span className="career-card-role">{app.role}</span>
      <span className="career-card-company">{app.company}</span>
      <span className="career-card-meta">
        <span className="career-figure">{formatDate(app.date_applied)}</span>
        {app.salary_range && <span>{app.salary_range}</span>}
        {app.created_by && <span>via {app.created_by}</span>}
      </span>
    </div>
  );
}

function PipelineBoard({ applications, onOpen, onMove }) {
  const [dragId, setDragId] = useState(null);
  const [overStatus, setOverStatus] = useState(null);

  return (
    <div className="career-board" role="list" aria-label="Application pipeline">
      {STATUSES.map(({ id, label }) => {
        const items = applications.filter(a => a.status === id);
        return (
          <section
            key={id}
            role="listitem"
            aria-labelledby={`career-col-${id}`}
            className={`career-column ${overStatus === id ? 'is-drop-target' : ''}`}
            onDragOver={e => { if (dragId != null) { e.preventDefault(); setOverStatus(id); } }}
            onDragLeave={e => { if (!e.currentTarget.contains(e.relatedTarget)) setOverStatus(null); }}
            onDrop={e => {
              e.preventDefault();
              const appId = Number(e.dataTransfer.getData('text/plain'));
              setOverStatus(null);
              setDragId(null);
              const app = applications.find(a => a.id === appId);
              if (app && app.status !== id) onMove(appId, id);
            }}
          >
            <header className="career-column-header">
              <h3 id={`career-col-${id}`} className="career-column-title">
                <span className={`career-status-dot status-${id}`} aria-hidden="true" />
                {label}
              </h3>
              <span className="career-column-count career-figure">{items.length}</span>
            </header>
            <div className="career-column-body">
              {items.length === 0 ? (
                <p className="career-empty">None</p>
              ) : items.map(app => (
                <ApplicationCard
                  key={app.id}
                  app={app}
                  onOpen={onOpen}
                  onDragStart={setDragId}
                  onDragEnd={() => { setDragId(null); setOverStatus(null); }}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function LeadsPanel({ leads, onPromote, onDismiss, onAdd, busyId }) {
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(EMPTY_LEAD);
  const [saving, setSaving] = useState(false);
  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setSaving(true);
    const ok = await onAdd(form);
    setSaving(false);
    if (ok) { setForm(EMPTY_LEAD); setAdding(false); }
  };

  return (
    <div className="glass-panel">
      <div className="panel-header">
        <h2 className="panel-title">Open leads</h2>
        <button type="button" className="btn-secondary" onClick={() => setAdding(a => !a)} aria-expanded={adding}>
          {adding ? 'Cancel' : 'Add lead'}
        </button>
      </div>
      <div className="panel-content career-panel-content">
        {adding && (
          <form className="career-lead-form" onSubmit={submit}>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="lead-company">Company</label>
                <input id="lead-company" className="form-input" value={form.company} onChange={set('company')} required autoFocus />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="lead-role">Role</label>
                <input id="lead-role" className="form-input" value={form.role} onChange={set('role')} required />
              </div>
            </div>
            <div className="form-group career-form-row">
              <label className="form-label" htmlFor="lead-url">Job listing URL</label>
              <input id="lead-url" type="url" className="form-input" placeholder="https://" value={form.job_url} onChange={set('job_url')} required />
            </div>
            <div className="form-grid">
              <div className="form-group">
                <label className="form-label" htmlFor="lead-location">Location</label>
                <input id="lead-location" className="form-input" placeholder="Remote" value={form.location} onChange={set('location')} />
              </div>
              <div className="form-group">
                <label className="form-label" htmlFor="lead-salary">Salary range</label>
                <input id="lead-salary" className="form-input" placeholder="$120k–$150k" value={form.salary_range} onChange={set('salary_range')} />
              </div>
            </div>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Adding…' : 'Add lead'}</button>
          </form>
        )}

        {leads.length === 0 ? (
          <p className="career-empty">No open leads. Your agents add them here, or add one yourself.</p>
        ) : (
          <ul className="item-list career-lead-list">
            {leads.map(lead => (
              <li key={lead.id} className="list-item career-lead">
                <div className="item-meta">
                  <span className="item-title">{lead.role}</span>
                  <span className="item-subtitle">
                    {[lead.company, lead.location, lead.salary_range].filter(Boolean).join(' · ')}
                  </span>
                  <span className="item-subtitle">
                    {lead.job_url && (
                      <a href={lead.job_url} target="_blank" rel="noopener noreferrer" className="career-link">View listing</a>
                    )}
                    {lead.match_score > 0 && <span> · {lead.match_score}% match</span>}
                    {lead.created_by && <span> · via {lead.created_by}</span>}
                  </span>
                </div>
                <div className="career-lead-actions">
                  <button type="button" className="btn-secondary" disabled={busyId === lead.id} onClick={() => onDismiss(lead)}>
                    Dismiss
                  </button>
                  <button type="button" className="btn-primary career-btn-sm" disabled={busyId === lead.id} onClick={() => onPromote(lead)}>
                    Mark applied
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function LogApplicationDialog({ open, onClose, onSubmit }) {
  const ref = useDialog(open, onClose);
  const [saving, setSaving] = useState(false);
  if (!open) return null;

  const submit = async (e) => {
    e.preventDefault();
    const form = e.target;
    const payload = {};
    ['company', 'role', 'date_applied', 'status', 'job_description_url', 'salary_range', 'recruiter_name', 'recruiter_email', 'notes']
      .forEach(k => { if (form[k].value.trim()) payload[k] = form[k].value.trim(); });
    setSaving(true);
    const ok = await onSubmit(payload);
    setSaving(false);
    if (ok) onClose();
  };

  return (
    <div className="athena-modal-overlay" onClick={onClose}>
      <div
        ref={ref}
        className="athena-modal-card career-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="career-log-title"
        onClick={e => e.stopPropagation()}
      >
        <div className="career-sheet-header">
          <h2 id="career-log-title" className="career-sheet-title">Log application</h2>
          <button type="button" className="career-icon-btn" aria-label="Close" onClick={onClose}>
            <span className="material-symbols-outlined" aria-hidden="true">close</span>
          </button>
        </div>
        <form className="career-sheet-body" onSubmit={submit}>
          <p className="career-hint">If you already logged this job (same link, or same company and role within 90 days), it's updated instead.</p>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label" htmlFor="log-company">Company</label>
              <input id="log-company" name="company" className="form-input" required data-autofocus />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="log-role">Role</label>
              <input id="log-role" name="role" className="form-input" required />
            </div>
          </div>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label" htmlFor="log-date">Date applied</label>
              <input id="log-date" name="date_applied" type="date" className="form-input" defaultValue={today()} required />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="log-status">Status</label>
              <select id="log-status" name="status" className="form-select" defaultValue="applied">
                {STATUSES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group career-form-row">
            <label className="form-label" htmlFor="log-url">Job listing URL</label>
            <input id="log-url" name="job_description_url" type="url" className="form-input" placeholder="https://" />
          </div>
          <div className="form-group career-form-row">
            <label className="form-label" htmlFor="log-salary">Salary range</label>
            <input id="log-salary" name="salary_range" className="form-input" />
          </div>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label" htmlFor="log-rname">Recruiter name</label>
              <input id="log-rname" name="recruiter_name" className="form-input" />
            </div>
            <div className="form-group">
              <label className="form-label" htmlFor="log-remail">Recruiter email</label>
              <input id="log-remail" name="recruiter_email" type="email" className="form-input" />
            </div>
          </div>
          <div className="form-group career-form-row">
            <label className="form-label" htmlFor="log-notes">Notes</label>
            <textarea id="log-notes" name="notes" rows={3} className="form-textarea" />
          </div>
          <div className="career-sheet-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Log application'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Timeline({ events }) {
  if (!events?.length) return <p className="career-empty">Nothing on the timeline yet.</p>;
  const ordered = [...events].reverse();
  return (
    <ol className="career-timeline">
      {ordered.map(ev => (
        <li key={ev.id} className="career-timeline-item">
          <div className="career-timeline-head">
            <span className="career-timeline-kind">{EVENT_LABEL[ev.kind] || ev.kind}</span>
            <span className="career-figure">{formatDate(ev.event_date)}</span>
          </div>
          {ev.note && <p className="career-timeline-note">{ev.note}</p>}
          {ev.created_by && <span className="career-timeline-by">by {ev.created_by}</span>}
        </li>
      ))}
    </ol>
  );
}

function ApplicationDrawer({ app, onClose, onSave, onStatus, onAddEvent, onDelete }) {
  // Keyed by application id, so this state resets when a different application opens
  const ref = useDialog(true, onClose);
  const [fields, setFields] = useState(() => Object.fromEntries(APP_FIELDS.map(k => [k, app[k] || ''])));
  const [eventForm, setEventForm] = useState({ kind: 'interview', event_date: today(), note: '' });
  const [saving, setSaving] = useState(false);
  const [addingEvent, setAddingEvent] = useState(false);

  const set = (key) => (e) => setFields(f => ({ ...f, [key]: e.target.value }));
  const changed = APP_FIELDS.filter(k => (fields[k] ?? '') !== (app[k] || ''));
  // The API ignores blank values, so a field can be changed but not emptied
  const cleared = changed.filter(k => !fields[k]?.trim());

  const save = async (e) => {
    e.preventDefault();
    if (changed.length === 0 || cleared.length > 0) return;
    setSaving(true);
    await onSave(app.id, Object.fromEntries(changed.map(k => [k, fields[k]])));
    setSaving(false);
  };

  const addEvent = async (e) => {
    e.preventDefault();
    setAddingEvent(true);
    const ok = await onAddEvent(app.id, eventForm);
    setAddingEvent(false);
    if (ok) setEventForm(f => ({ ...f, note: '' }));
  };

  const field = (key, label, props = {}) => (
    <div className="form-group">
      <label className="form-label" htmlFor={`app-${key}`}>{label}</label>
      <input id={`app-${key}`} className="form-input" value={fields[key] ?? ''} onChange={set(key)} {...props} />
    </div>
  );

  return (
    <div className="athena-modal-overlay career-drawer-overlay" onClick={onClose}>
      <aside
        ref={ref}
        className="athena-modal-card career-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="career-drawer-title"
        onClick={e => e.stopPropagation()}
      >
        <div className="career-sheet-header">
          <div className="career-drawer-heading">
            <h2 id="career-drawer-title" className="career-sheet-title">{app.role}</h2>
            <span className="career-drawer-sub">
              {app.company}
              {app.created_by && ` · logged by ${app.created_by}`}
            </span>
          </div>
          <button type="button" className="career-icon-btn" aria-label="Close details" onClick={onClose}>
            <span className="material-symbols-outlined" aria-hidden="true">close</span>
          </button>
        </div>

        <div className="career-sheet-body">
          <div className="form-group career-form-row">
            <label className="form-label" htmlFor="app-status">Status</label>
            <select id="app-status" className="form-select" value={app.status} onChange={e => onStatus(app.id, e.target.value)} data-autofocus>
              {STATUSES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>

          <section className="career-drawer-section" aria-labelledby="career-details-title">
            <h3 id="career-details-title" className="career-section-title">Details</h3>
            <form onSubmit={save}>
              <div className="form-grid">
                {field('company', 'Company', { required: true })}
                {field('role', 'Role', { required: true })}
              </div>
              <div className="form-grid">
                {field('date_applied', 'Date applied', { type: 'date', required: true })}
                {field('salary_range', 'Salary range')}
              </div>
              <div className="form-group career-form-row">
                <label className="form-label" htmlFor="app-job_description_url">
                  Job listing URL
                  {app.job_description_url && (
                    <> · <a href={app.job_description_url} target="_blank" rel="noopener noreferrer" className="career-link">Open</a></>
                  )}
                </label>
                <input id="app-job_description_url" type="url" className="form-input" value={fields.job_description_url ?? ''} onChange={set('job_description_url')} />
              </div>
              <div className="form-grid">
                {field('recruiter_name', 'Recruiter name')}
                {field('recruiter_email', 'Recruiter email', { type: 'email' })}
              </div>
              <div className="form-group career-form-row">
                <label className="form-label" htmlFor="app-notes">Notes</label>
                <textarea id="app-notes" rows={3} className="form-textarea" value={fields.notes ?? ''} onChange={set('notes')} />
              </div>
              {cleared.length > 0 && (
                <p className="career-hint career-form-row" role="status">
                  A field can't be emptied yet. Type a new value, or undo the change.
                </p>
              )}
              <button type="submit" className="btn-primary" disabled={saving || changed.length === 0 || cleared.length > 0}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </form>
          </section>

          <section className="career-drawer-section" aria-labelledby="career-timeline-title">
            <h3 id="career-timeline-title" className="career-section-title">Timeline</h3>
            <form className="career-event-form" onSubmit={addEvent}>
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label" htmlFor="event-kind">Type</label>
                  <select id="event-kind" className="form-select" value={eventForm.kind} onChange={e => setEventForm(f => ({ ...f, kind: e.target.value }))}>
                    {EVENT_KINDS.map(k => <option key={k.id} value={k.id}>{k.label}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label" htmlFor="event-date">Date</label>
                  <input id="event-date" type="date" className="form-input" value={eventForm.event_date} onChange={e => setEventForm(f => ({ ...f, event_date: e.target.value }))} required />
                </div>
              </div>
              <div className="form-group career-form-row">
                <label className="form-label" htmlFor="event-note">Note</label>
                <input id="event-note" className="form-input" placeholder="Phone screen with the hiring manager" value={eventForm.note} onChange={e => setEventForm(f => ({ ...f, note: e.target.value }))} />
              </div>
              <button type="submit" className="btn-secondary" disabled={addingEvent}>{addingEvent ? 'Adding…' : 'Add to timeline'}</button>
            </form>
            <Timeline events={app.events} />
          </section>

          <section className="career-drawer-section">
            <button type="button" className="btn-danger" onClick={() => onDelete(app)}>
              <span className="material-symbols-outlined" aria-hidden="true">delete</span>
              Delete application
            </button>
          </section>
        </div>
      </aside>
    </div>
  );
}

function CareerTab({ careerData, renderRelatedAreas, showToast }) {
  const [data, setData] = useState(careerData || { applications: [], leads: [], stats: {} });
  const [syncedProp, setSyncedProp] = useState(careerData);
  const [openId, setOpenId] = useState(null);
  const [logOpen, setLogOpen] = useState(false);
  const [busyLeadId, setBusyLeadId] = useState(null);

  // Take a fresh snapshot when the app-wide refresh delivers one
  if (careerData && careerData !== syncedProp) {
    setSyncedProp(careerData);
    setData(careerData);
  }

  const refresh = useCallback(async () => {
    try {
      setData(await request('/career'));
    } catch {
      showToast("Couldn't refresh career data. Check the connection and reload.", 'error');
    }
  }, [showToast]);

  // Runs a mutation, refreshes, and reports. Returns true on success.
  const mutate = async (fn, success, failure) => {
    try {
      const res = await fn();
      await refresh();
      if (success) showToast(typeof success === 'function' ? success(res) : success, 'success');
      return true;
    } catch (err) {
      showToast(`${failure} ${err.message || ''}`.trim(), 'error');
      return false;
    }
  };

  const moveApplication = (id, status) => {
    // Optimistic move so the card lands where it was dropped
    setData(d => ({ ...d, applications: d.applications.map(a => (a.id === id ? { ...a, status } : a)) }));
    return mutate(
      () => request(`/career/applications/${id}`, 'PUT', { status }),
      `Moved to ${STATUS_LABEL[status].toLowerCase()}.`,
      "Couldn't move that application.",
    );
  };

  const saveApplication = (id, fields) => mutate(
    () => request(`/career/applications/${id}`, 'PUT', fields),
    'Changes saved.',
    "Couldn't save changes.",
  );

  const addEvent = (id, ev) => mutate(
    () => request(`/career/applications/${id}/events`, 'POST', { kind: ev.kind, event_date: ev.event_date, note: ev.note || null }),
    'Added to the timeline.',
    "Couldn't add that entry.",
  );

  const deleteApplication = async (app) => {
    if (!confirm(`Delete the ${app.role} application at ${app.company} and its timeline? This can't be undone.`)) return;
    const ok = await mutate(
      () => request(`/career/applications/${app.id}`, 'DELETE'),
      'Application deleted.',
      "Couldn't delete the application.",
    );
    if (ok) setOpenId(null);
  };

  const logApplication = (payload) => mutate(
    () => request('/career', 'POST', payload),
    res => (res.result === 'updated'
      ? 'That job was already logged, so its entry was updated.'
      : `Logged ${payload.role} at ${payload.company}.`),
    "Couldn't log the application.",
  );

  const addLead = (lead) => mutate(
    () => request('/career/leads', 'POST', Object.fromEntries(Object.entries(lead).filter(([, v]) => v.trim()))),
    res => (res.result === 'updated' ? 'That listing was already a lead, so it was updated.' : 'Lead added.'),
    "Couldn't add the lead.",
  );

  const promoteLead = async (lead) => {
    setBusyLeadId(lead.id);
    await mutate(
      () => request(`/career/leads/${lead.id}/promote`, 'POST', {}),
      res => (res.result === 'updated'
        ? `Matched an existing ${lead.company} application and linked the lead.`
        : `Logged ${lead.role} at ${lead.company} as applied.`),
      "Couldn't mark that lead applied.",
    );
    setBusyLeadId(null);
  };

  const dismissLead = async (lead) => {
    setBusyLeadId(lead.id);
    await mutate(
      () => request(`/career/leads/${lead.id}/ignore`, 'POST'),
      `Dismissed ${lead.role} at ${lead.company}.`,
      "Couldn't dismiss that lead.",
    );
    setBusyLeadId(null);
  };

  const applications = data.applications || [];
  const leads = data.leads || [];
  const stats = data.stats || {};
  const openApp = applications.find(a => a.id === openId) || null;

  return (
    <div>
      <header className="page-header page-header--compact">
        <h1 className="page-title">Career</h1>
        <div className="page-header-meta">
          <p className="page-subtitle">
            {plural(stats.active_applications || 0, 'active', 'active')} · {plural(stats.by_status?.offered || 0, 'offer')} · {plural(stats.open_leads ?? leads.length, 'open lead')}
          </p>
          <button type="button" className="btn-primary" onClick={() => setLogOpen(true)}>
            <span className="material-symbols-outlined" aria-hidden="true">add</span>
            Log application
          </button>
        </div>
      </header>

      <section className="career-board-section" aria-labelledby="career-pipeline-title">
        <div className="career-board-heading">
          <h2 id="career-pipeline-title" className="panel-title">Pipeline</h2>
          <span className="career-hint career-hint--desktop">Drag a card to change its status, or open it for details.</span>
          <span className="career-hint career-hint--touch">Tap a card for details and to change its status.</span>
        </div>
        {applications.length === 0 ? (
          <div className="glass-panel career-board-empty">
            <p className="career-empty">No applications yet. Log one, or mark a lead applied.</p>
          </div>
        ) : (
          <PipelineBoard applications={applications} onOpen={setOpenId} onMove={moveApplication} />
        )}
      </section>

      <div className="grid-2col career-lower">
        <LeadsPanel
          leads={leads}
          onPromote={promoteLead}
          onDismiss={dismissLead}
          onAdd={addLead}
          busyId={busyLeadId}
        />
        <div>{renderRelatedAreas('Career')}</div>
      </div>

      {openApp && (
        <ApplicationDrawer
          key={openApp.id}
          app={openApp}
          onClose={() => setOpenId(null)}
          onSave={saveApplication}
          onStatus={moveApplication}
          onAddEvent={addEvent}
          onDelete={deleteApplication}
        />
      )}
      <LogApplicationDialog open={logOpen} onClose={() => setLogOpen(false)} onSubmit={logApplication} />
    </div>
  );
}

export default CareerTab;
