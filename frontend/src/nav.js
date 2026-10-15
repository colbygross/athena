// Single source of truth for navigation, shared by the desktop sidebar and the mobile tab bar.
export const NAV_SECTIONS = [
  {
    id: 'today',
    label: 'Today',
    items: [
      { id: 'overview', icon: 'dashboard', label: 'Overview', accent: 'cyan' },
      { id: 'daily-briefs', icon: 'description', label: 'Daily Briefs', accent: 'cyan' },
      { id: 'calendar-tasks', icon: 'calendar_today', label: 'Calendar & Tasks', accent: 'cyan' },
      { id: 'inbox', icon: 'move_to_inbox', label: 'Inbox', accent: 'cyan' },
    ],
  },
  {
    id: 'life',
    label: 'Life',
    items: [
      { id: 'finances', icon: 'attach_money', label: 'Finances', accent: 'pink' },
      { id: 'fitness', icon: 'favorite', label: 'Health & Fitness', accent: 'green' },
      { id: 'learning', icon: 'school', label: 'Learning', accent: 'purple' },
      { id: 'career', icon: 'work', label: 'Career', accent: 'yellow' },
      { id: 'habits', icon: 'sync', label: 'Habits', accent: 'green' },
    ],
  },
  {
    id: 'vault',
    label: 'Vault',
    items: [
      { id: 'projects', icon: 'folder', label: 'Projects', accent: 'purple' },
      { id: 'areas', icon: 'folder_shared', label: 'Areas', accent: 'purple' },
      { id: 'resources', icon: 'folder_special', label: 'Resources', accent: 'purple' },
    ],
  },
];

export const NAV_ITEMS = NAV_SECTIONS.flatMap(section => section.items);

// Mobile tab bar: four primary destinations plus "More".
export const MOBILE_TABS = [
  { id: 'overview', icon: 'today', label: 'Today' },
  { id: 'calendar-tasks', icon: 'calendar_today', label: 'Calendar' },
  { id: 'finances', icon: 'attach_money', label: 'Money' },
  { id: 'fitness', icon: 'favorite', label: 'Health' },
];

export const navLabel = (item, inboxCount) =>
  item.id === 'inbox' && inboxCount > 0 ? `${item.label} (${inboxCount})` : item.label;
