import { useRef } from 'react';
import { HABITS, formatLocalDate } from '../constants';
import { parseDailyBrief } from './BriefPanel';
import QuickLog from './QuickLog';

const PRIORITY_RANK = { high: 0, medium: 1, low: 2 };
const byPriority = (a, b) => (PRIORITY_RANK[a.priority] ?? 1) - (PRIORITY_RANK[b.priority] ?? 1);
const dayOf = (value) => (value || '').replace('T', ' ').slice(0, 10);
const timeOf = (value) => (value || '').replace('T', ' ').slice(11, 16);
const money = (amount) => `$${amount.toFixed(2)}`;

function Skeleton() {
  return <div className="overview-skeleton" aria-hidden="true" />;
}

function EmptyState({ message, actionLabel, onAction }) {
  return (
    <div className="overview-empty">
      <p>{message}</p>
      {actionLabel && (
        <button type="button" className="btn-secondary" onClick={onAction}>{actionLabel}</button>
      )}
    </div>
  );
}

function TaskRow({ task, toggleTask, overdue }) {
  const meta = overdue
    ? <span className="today-flag"><span className="material-symbols-outlined" aria-hidden="true">warning</span>Overdue • due {task.due_date}</span>
    : <span className="today-meta">{[task.category, task.priority && `${task.priority} priority`].filter(Boolean).join(' • ')}</span>;

  return (
    <li className="today-task">
      <label className="today-task-label">
        <input type="checkbox" className="today-checkbox" checked={false} onChange={() => toggleTask(task.id)} />
        <span>{task.title}</span>
      </label>
      <div className="today-task-meta">{meta}</div>
    </li>
  );
}

function OverviewTab({
  overviewData,
  tasksData,
  calendarData,
  selectedBrief,
  dailyBriefsList,
  dataError,
  toggleTask,
  fetchAllData,
  setActiveTab,
  fileUrl,
  handleFormSubmit,
  showToast,
  API_BASE,
}) {
  const quickLogRef = useRef(null);
  const now = new Date();
  const today = formatLocalDate(now);
  const nowTime = now.toTimeString().slice(0, 5);
  const loaded = Boolean(overviewData);

  // Live data for the Today panel. The brief is a snapshot from the night before, so it only supplies the workout.
  const todaysEvents = (calendarData || [])
    .filter(ev => dayOf(ev.start_time) === today)
    .sort((a, b) => a.start_time.localeCompare(b.start_time));
  const nextEvent = todaysEvents.find(ev => timeOf(ev.start_time) >= nowTime);

  const pending = (tasksData || []).filter(t => t.status === 'pending');
  const overdue = pending.filter(t => t.due_date && t.due_date < today).sort(byPriority);
  const dueToday = pending.filter(t => t.due_date === today).sort(byPriority);

  // briefs[0] can be tomorrow's brief (the nightly job writes it around 03:15), so match today's date explicitly.
  const briefs = dailyBriefsList || [];
  const briefIsToday = selectedBrief?.date === today;
  const workout = briefIsToday ? parseDailyBrief(selectedBrief.content)?.workout : null;
  const hasWorkout = Boolean(workout?.routine);
  const tomorrowBriefReady = !briefs.some(b => b.date === today) && briefs.some(b => b.date > today);

  const todaysHabits = overviewData?.todays_habits || [];
  const isHabitDone = (name) => todaysHabits.some(h => h.habit_name === name && h.completed === 1);
  const habitsDone = HABITS.filter(isHabitDone).length;
  const toggleHabit = (name, done) => handleFormSubmit(
    'habits',
    { date: today, habit_name: name, completed: done ? 0 : 1, notes: 'Quick logged from dashboard' },
    () => {},
    {}
  );

  let summary;
  if (dataError) {
    summary = "Couldn't load today";
  } else if (!loaded) {
    summary = 'Loading today';
  } else {
    const parts = [];
    if (dueToday.length) parts.push(`${dueToday.length} due today`);
    if (overdue.length) parts.push(`${overdue.length} overdue`);
    if (nextEvent) parts.push(`next event ${timeOf(nextEvent.start_time)}`);
    summary = parts.length ? parts.join(' • ') : 'Nothing scheduled. A clear day.';
  }

  const week = loaded ? {
    spend: overviewData.monthly_expense,
    workouts: overviewData.weekly_workouts,
    hours: overviewData.weekly_learning_hours,
    jobs: overviewData.active_jobs,
  } : null;
  const weekIsEmpty = week && !week.spend && !week.workouts && !week.hours && !week.jobs;

  const focusQuickLog = () => quickLogRef.current?.focus();

  return (
    <div>
      <header className="page-header">
        <time className="page-date" dateTime={today}>
          {now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
        </time>
        <h1 className="page-title">Overview</h1>
        <p className="page-subtitle">{summary}</p>
      </header>

      {/* Today: the first thing on screen */}
      <section className="glass-panel today-panel" aria-labelledby="today-heading">
        <div className="panel-header">
          <h2 id="today-heading" className="panel-title">Today</h2>
        </div>

        {dataError ? (
          <div className="overview-notice" role="alert">
            <span className="material-symbols-outlined" aria-hidden="true">cloud_off</span>
            <p>Couldn't reach Athena, so this may be out of date.</p>
            <button type="button" className="btn-secondary" onClick={fetchAllData}>Retry</button>
          </div>
        ) : !loaded ? (
          <div className="today-body" role="status" aria-busy="true">
            <span className="sr-only">Loading today</span>
            <div className="today-col-tasks">
              <Skeleton />
              <Skeleton />
            </div>
            <Skeleton />
          </div>
        ) : (
          <div className="today-body">
            <div className="today-col-tasks">
              {overdue.length > 0 && (
                <section className="today-overdue" aria-labelledby="today-overdue-heading">
                  <h3 id="today-overdue-heading" className="overview-heading overview-heading-danger">Overdue</h3>
                  <ul className="today-list">
                    {overdue.map(task => (
                      <TaskRow key={task.id} task={task} toggleTask={toggleTask} overdue />
                    ))}
                  </ul>
                </section>
              )}

              <section className="today-due" aria-labelledby="today-due-heading">
                <h3 id="today-due-heading" className="overview-heading">Due today</h3>
                {dueToday.length > 0 ? (
                  <ul className="today-list">
                    {dueToday.map(task => (
                      <TaskRow key={task.id} task={task} toggleTask={toggleTask} />
                    ))}
                  </ul>
                ) : overdue.length > 0 ? (
                  <p className="today-empty">Nothing else due today.</p>
                ) : (
                  <EmptyState
                    message="No tasks due. You're clear."
                    actionLabel="Add task"
                    onAction={() => setActiveTab('calendar-tasks')}
                  />
                )}
              </section>

              {hasWorkout && (
                <section className="today-workout" aria-labelledby="today-workout-heading">
                  <h3 id="today-workout-heading" className="overview-heading">Workout</h3>
                  <p className="today-workout-routine">{workout.routine}</p>
                  {workout.exercises.length > 0 && (
                    <ul className="today-list">
                      {workout.exercises.map((ex, idx) => (
                        <li key={idx} className={`today-exercise ${ex.completed ? 'is-done' : ''}`}>
                          <span className="material-symbols-outlined" aria-hidden="true">
                            {ex.completed ? 'check_box' : 'check_box_outline_blank'}
                          </span>
                          <span>{ex.name}</span>
                          {ex.completed && <span className="sr-only">(done)</span>}
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              )}
            </div>

            <section className="today-schedule" aria-labelledby="today-schedule-heading">
              <h3 id="today-schedule-heading" className="overview-heading">Schedule</h3>
              {todaysEvents.length > 0 ? (
                <ol className="today-list">
                  {todaysEvents.map(ev => (
                    <li key={ev.id} className="today-event">
                      <span className="today-time">{timeOf(ev.start_time)}</span>
                      <span className="today-event-title">{ev.title}</span>
                      {ev === nextEvent && <span className="today-next">Next</span>}
                    </li>
                  ))}
                </ol>
              ) : (
                <EmptyState
                  message="Nothing on the calendar today."
                  actionLabel="Add event"
                  onAction={() => setActiveTab('calendar-tasks')}
                />
              )}
            </section>
          </div>
        )}

        {loaded && tomorrowBriefReady && (
          <p className="today-footnote">
            Tomorrow's brief is ready.{' '}
            <button type="button" className="overview-text-button" onClick={() => setActiveTab('daily-briefs')}>
              Open Daily Briefs
            </button>
          </p>
        )}
      </section>

      <QuickLog API_BASE={API_BASE} showToast={showToast} onLogged={fetchAllData} inputRef={quickLogRef} />

      {/* Habits: real toggle buttons */}
      <section className="glass-panel overview-habits" aria-labelledby="habits-heading">
        <div className="panel-header">
          <h2 id="habits-heading" className="panel-title">Habits today</h2>
          <button type="button" className="btn-secondary" onClick={() => setActiveTab('habits')}>View streaks</button>
        </div>
        <div className="panel-content">
          {loaded && (
            <p className="overview-habits-count">
              {habitsDone === 0 ? 'Tap a habit to log it for today.' : `${habitsDone} of ${HABITS.length} done`}
            </p>
          )}
          <div className="habits-grid">
            {HABITS.map(name => {
              const done = isHabitDone(name);
              return (
                <button
                  type="button"
                  key={name}
                  className={`glass-panel habit-card ${done ? 'completed' : ''}`}
                  aria-pressed={done}
                  onClick={() => toggleHabit(name, done)}
                >
                  <span className="habit-checkbox material-symbols-outlined" aria-hidden="true">check</span>
                  <span className="habit-title">{name}</span>
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* This week: quiet secondary row */}
      <section className="overview-week" aria-labelledby="week-heading">
        <h2 id="week-heading" className="overview-heading">This week</h2>
        {!week ? (
          !dataError && <Skeleton />
        ) : weekIsEmpty ? (
          <EmptyState message="No activity logged this week." />
        ) : (
          <div className="week-row">
            <button type="button" className="week-stat" onClick={() => setActiveTab('finances')}>
              <span className="week-stat-label">Spent this month</span>
              <span className={`week-stat-value ${week.spend ? '' : 'is-empty'}`}>
                {week.spend ? money(week.spend) : 'Nothing logged'}
              </span>
            </button>
            <button type="button" className="week-stat" onClick={() => setActiveTab('fitness')}>
              <span className="week-stat-label">Workouts, 7 days</span>
              <span className={`week-stat-value ${week.workouts ? '' : 'is-empty'}`}>
                {week.workouts ? `${week.workouts} sessions` : 'No sessions'}
              </span>
            </button>
            <button type="button" className="week-stat" onClick={() => setActiveTab('learning')}>
              <span className="week-stat-label">Study, 7 days</span>
              <span className={`week-stat-value ${week.hours ? '' : 'is-empty'}`}>
                {week.hours ? `${week.hours} hrs` : 'No study logged'}
              </span>
            </button>
            <button type="button" className="week-stat" onClick={() => setActiveTab('career')}>
              <span className="week-stat-label">Applications</span>
              <span className={`week-stat-value ${week.jobs ? '' : 'is-empty'}`}>
                {week.jobs ? `${week.jobs} active` : 'No applications'}
              </span>
            </button>
          </div>
        )}
      </section>

      {/* Recent activity: the top three of each */}
      <div className="grid-2col">
        <div className="glass-panel">
          <div className="panel-header">
            <h2 className="panel-title">Recent transactions</h2>
            <button type="button" className="btn-secondary" onClick={() => setActiveTab('finances')}>View all</button>
          </div>
          <div className="panel-content">
            {!loaded ? (
              !dataError && <Skeleton />
            ) : overviewData.recent_transactions.length === 0 ? (
              <EmptyState message="No transactions yet." actionLabel="Log an expense" onAction={focusQuickLog} />
            ) : (
              <div className="item-list">
                {overviewData.recent_transactions.slice(0, 3).map((tx) => (
                  <div key={tx.id} className="list-item">
                    <div className="item-meta">
                      <span className="item-title">{tx.merchant || "Unknown merchant"}</span>
                      <span className="item-subtitle">{tx.date} • {tx.category}</span>
                    </div>
                    <div className="overview-tx-end">
                      <span className={`badge badge-${tx.type}`}>{tx.type.toUpperCase()}</span>
                      <span className={`item-value ${tx.type === 'expense' ? 'amount-expense' : tx.type === 'transfer' ? 'amount-transfer' : 'amount-income'}`}>
                        {money(tx.amount)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel">
          <div className="panel-header">
            <h2 className="panel-title">Recently sorted files</h2>
            <button type="button" className="btn-secondary" onClick={() => setActiveTab('inbox')}>Inbox</button>
          </div>
          <div className="panel-content">
            {!loaded ? (
              !dataError && <Skeleton />
            ) : overviewData.recent_files.length === 0 ? (
              <EmptyState
                message="Drop files into the vault's Inbox folder and Athena will sort them."
                actionLabel="Open Inbox"
                onAction={() => setActiveTab('inbox')}
              />
            ) : (
              <div className="item-list">
                {overviewData.recent_files.slice(0, 3).map((file) => (
                  <a key={file.id} href={fileUrl(file.new_path)} target="_blank" rel="noopener noreferrer" className="list-item overview-file-link">
                    <div className="item-meta">
                      <span className="item-title">{file.original_name}</span>
                      <span className="item-subtitle">Sorted to: {file.category.toUpperCase()}</span>
                    </div>
                    <span className="material-symbols-outlined file-icon" aria-hidden="true">description</span>
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default OverviewTab;
