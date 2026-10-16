// Base URL for the Athena API. Production serves the UI and API from the same origin.
// For local `npm run dev` (Vite on 5173) set VITE_API_URL or run the backend on :8000.
export const API_BASE = import.meta.env.VITE_API_URL || (
  window.location.port === '5173'
    ? `http://${window.location.hostname}:8000/api`
    : `${window.location.origin}/api`
);
