# Stitch Design System & Styling Guide

Athena OS uses the **Stitch Design System**—a custom visual framework inspired by diagnostic command cockpits and tactical HUD readouts. It combines a dark, low-contrast background palette with glowing neon accents, blocky geometric borders, and monospace telemetries.

---

## 1. Color Palette Variables

The system relies on CSS variables declared in [index.css](../frontend/src/index.css#L17-L49) for both dark and light modes. Below is the active dark mode color configuration:

| CSS Variable | Value | Purpose |
| :--- | :--- | :--- |
| `--bg-space` | `#070a12` | Obsidian base canvas. Reduces eye strain. |
| `--bg-surface` | `#10131c` | Outer boundary surfaces. |
| `--bg-card` | `#181b24` | Primary card panels (solid deep slate). |
| `--bg-card-hover` | `#272a33` | Elevated card highlight background on hover. |
| `--accent-cyan` | `#00f2fe` | Cortana Cyan: Hermes/agent telemetry, active links, main headers. |
| `--accent-green` | `#39ff14` | DedSec Toxic Green: Successful metrics, completed database logs, workouts. |
| `--accent-pink` | `#ff007f` | Cyber Pink: Alerts, liabilities, budget overrun warning, delete buttons. |
| `--accent-purple` | `#7b61ff` | Cyber Purple: Learning categories, study hours, wellbeing dial indicator. |
| `--text-primary` | `#e0e2ee` | High-contrast body text. |
| `--text-secondary` | `#b9cacb` | Sub-labels and metadata. |
| `--text-muted` | `#849495` | Low-contrast comments, labels, inactive indicators. |

---

## 2. Typography & Fonts

Athena OS overrides default browser typography using two premium custom fonts loaded locally in [index.css](../frontend/src/index.css#L1-L15):

```css
@font-face {
  font-family: 'KH Interference';
  src: url('./assets/fonts/KHInterferenceTRIAL-Regular.woff2') format('woff2');
}
@font-face {
  font-family: 'PP Fraktion Mono';
  src: url('./assets/fonts/PPFraktionMono-Regular-BF675904a6a1564.otf') format('opentype');
}
```

### Typographic Classes & Standard Rules:
1.  **Display Headers (`--font-display` / `'KH Interference'`)**:
    *   Used for major headers, page titles, sidebar logo, and panel section labels.
    *   Often styled as uppercase with brackets for a diagnostic HUD look (e.g. `[ BIO_DIAGNOSTICS ]`).
2.  **Telemetry & Values (`--font-mono` / `'PP Fraktion Mono'`)**:
    *   Used for numbers, tables, lists, form labels, source code, lists of tasks, and all diagnostic logs.
    *   Ensures clean geometric spacing for numerical data fields.

---

## 3. UI Card & Widget Components

### 3.1. Glass Panels (`.glass-panel`)
All sections are organized inside a grid of `.glass-panel` components:
*   **Default State**: Backed by a solid dark background with a low-contrast cyan border (`var(--border-glass)`).
*   **Hover State**: Changes border color to vibrant neon cyan (`var(--border-glass-hover)`), applies an outer glowing drop-shadow (`var(--shadow-premium)`), and elevates the background color to a lighter slate grey (`var(--bg-card-hover)`).

```css
.glass-panel {
  background: var(--bg-card);
  border: var(--border-glass);
  border-radius: var(--border-radius); /* 0.5rem */
  transition: var(--transition-smooth); /* 0.25s cubic-bezier */
}
.glass-panel:hover {
  border: var(--border-glass-hover);
  box-shadow: var(--shadow-premium);
  background: var(--bg-card-hover);
}
```

### 3.2. Form Inputs & Selects
*   **Inputs**: Feature a pure black background (`#000000`) with a solid/dashed cyan border.
*   **Focus State**: Replaces the border with a Cyber Pink border and a pink glow.
*   **Checkboxes**: Styled as custom block-check elements utilizing Material Symbols icons (`check_box` vs `check_box_outline_blank`) rather than default HTML inputs.

### 3.3. Navigation Sidebar
*   Uses a blocky structure with solid accents.
*   **Active Tab**: Emits an outer neon green or cyan glow, and fills the tab background with low-opacity green/cyan and active high-contrast labels.
*   **Hover Tab**: Smoothly increases border opacity. Supports sidebar collapsing via state handlers in [App.jsx](../frontend/src/App.jsx).

---

## 4. Cybernetic Keyframe Animations

To establish a "living console" aesthetic without distracting the user, animations are limited to low-impact ambient cycles:

1.  **Tab Boot Flicker (`hologram-boot`)**:
    *   Triggered on tab selection. Performs a rapid opacity flicker (300ms) to simulate a holographic monitor rebooting.
    *   Declared as `@keyframes hologram-boot` and applied automatically to main tab panes.
2.  **ScanlineSweep (`scanline`)**:
    *   A full-screen vertical scanline swept across the viewport in a repeating 6-second cycle, laying down a subtle overlay grid layer.
3.  **Active Corner Pulse**:
    *   Small neon green indicator dots in the top-right corner of synchronizing widgets cycle through a soft glow pulse (`opacity: 0.4` to `1.0`).

---

## 5. Viewport Responsiveness

The responsive system manages high-resolution desktop terminals, tablets, and mobile views:
*   **Layout Grid (`.grid-health-tab`, `.grid-scheduler`)**: Defaults to double-column formats (typically `1.2fr 0.8fr`).
*   **Breakpoint (`1450px` or Portrait orientation)**: Grid structures automatically collapse into single-column layouts (`1fr`), adjusting margins and font-sizes dynamically via CSS media queries.
*   **Sidebar Toggle**: The navigation sidebar collapses into a minimal icon-only strip, increasing viewport space for the data panels.
