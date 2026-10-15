# Athena design system

Athena is a personal dashboard. It should read as a calm, finished tool: black or near-black surfaces, one warm accent, and plain words. This file describes the system as shipped in `frontend/src/index.css`.

## Themes

Stark Dark is the default. Stark Light, Soft Dark and Soft Light are set with a class on `<html>`. Every color below is a token on `:root` (or a theme class), so components never hard-code color.

## Color

| Token | Stark Dark | Stark Light | Use |
| --- | --- | --- | --- |
| `--text-primary` | `#FFFFFF` (21:1) | `#0A0A0A` | Body and headings |
| `--text-secondary` | `#B0B0B0` (9.7:1) | `#333333` | Labels, secondary copy |
| `--text-muted` | `#8A8A8A` (6.1:1) | `#595959` | Captions, metadata |
| `--accent-wood` | `#A67B5B` | n/a | Brand accent |
| `--focus-ring` | `#C4956F` (7.9:1) | `#8A5A36` (5.8:1) | Keyboard focus |
| `--color-success` | `#5CC98A` (10.2:1) | `#15803D` | Income, done |
| `--color-danger` | `#F07A6E` (7.7:1) | `#B91C1C` | Overspend, errors |
| `--color-warning` | `#E0B25A` (10.7:1) | `#B45309` | Due soon, applied |

Surfaces are shade steps, not outlines:

| Token | Stark Dark | Stark Light | Use |
| --- | --- | --- | --- |
| `--surface-0` | `#000000` | `#FFFFFF` | Page |
| `--surface-1` | `#0E0E0E` | `#F5F5F7` | Panels, cards, list rows |
| `--surface-2` | `#161616` | `#ECECEF` | Hover, selected row, chips |

Soft themes define the same three steps. Tints of status colors are made with `color-mix(in srgb, var(--color-success) 12%, transparent)`, not hard-coded rgba.

Calendar event colors come from `EVENT_COLORS` in `src/constants.js`: six muted hues, shown as a small dot before the event title.

## Type

Three roles, defined as tokens:

- `--font-display` (KH Interference): page titles (`h1`, `.page-title`), the wordmark and large stat numbers. Nothing else.
- `--font-text` (system sans): all other text. Body, navigation, panel titles, buttons, labels, list items.
- `--font-mono` (PP Fraktion Mono): figures that must line up: amounts, times and durations, with `tabular-nums`.

Five sizes, and no others:

| Token | Size | Use |
| --- | --- | --- |
| `--text-xs` | 0.75rem (12px) | Captions, badges, metadata. This is the floor. |
| `--text-sm` | 0.875rem | Secondary body, form input |
| `--text-md` | 1rem | Body and list titles |
| `--text-lg` | 1.25rem | Panel titles |
| `--text-xl` | 2rem | Page titles and big numbers |

Labels are sentence case, with no uppercase and no letter-spacing.

## Surfaces and borders

- Panels, cards and list rows sit on `--surface-1` with no border. The shade change does the separating.
- Borders are allowed on form fields, tables, and the tab bar's top edge. Use `--border-cyan` (1px).
- Shadows are allowed only on things that float: dialogs, the toast stack and dropdowns.
- No gradients, glow, glass blur, side-stripe accents, or neon. The one exception is the mobile tab bar, which may blur its background.

## Focus, targets and motion

- `:focus-visible` draws a 2px `--focus-ring` outline with a 2px offset on every interactive element. Do not remove it.
- Text is 12px or larger.
- Icons are Material Symbols with `aria-hidden="true"`. Icon-only buttons have an `aria-label`.
- `prefers-reduced-motion` shortens all animations and transitions to near zero. Content stays; travel and pulses go.
- Dialogs trap focus and close on Escape.

## Copy

- Use the names people know: Inbox, Projects, Areas, Resources, Learning, Career, Habits, Health, Net worth.
- Sentence case for titles, labels and buttons. Buttons name the action: "Save changes", "Add task", "Run discovery".
- No emoji as UI. Use a Material Symbol with a text label, or text alone.
- Feedback is a toast (`showToast(message, 'success' | 'error')`), never `alert()`. Say what happened and what to do next. No "Error:" prefixes and no raw error objects.
- Destructive confirms say what will be removed and whether it can be undone: "Delete this task? This can't be undone."
