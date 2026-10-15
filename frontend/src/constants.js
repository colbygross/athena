// Shared between the Overview and Habits tabs so the habit list lives in one place.
export const HABITS = ['Code 1 Hour', 'Read 10 pages', 'Workout', 'Drink 3L Water', 'Sleep 8 hours'];

// Local calendar date as YYYY-MM-DD (toISOString would give the UTC date).
export const formatLocalDate = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

// Calendar event colors: muted, and readable on both themes.
export const EVENT_COLORS = ['#5B8FD9', '#3FAE8C', '#D9775B', '#A88BD6', '#D6A640', '#8E96A3'];
