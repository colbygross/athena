# Design System Document: Hermes Tactical Workspace

## 1. Overview & Creative North Star: "Neural Command HUD"
This design system represents a shared workspace between the user (Archer / Chief) and the AI companion (Hermes / Cortana). It bridges the gap between high-tech military HUDs and cybernetic hacker consoles.

**Creative North Star: Neural Command HUD**
The interface feels like a diagnostic cockpit: ultra-clean, structured, and clinically efficient, but with a living digital presence. The backdrop is comfortable for daily viewing, while key metrics and links pop with soft holographic glows.

**Core Design Principles:**
- **Shared Workspace**: Distinct indicators showing what Hermes is tracking vs. what the user enters.
- **Sophisticated Cybernetics**: No cartoonish glitching; animations are restricted to ambient pulses and clean transition flickers.
- **Data Denseness**: The layout packs diagnostic logs and charts tightly, separated by fine glowing dashed borders.

---

## 2. Colors: High-Contrast Tech-Noir
The color space uses a dark foundation with glowing cyan and acid-green accents to represent the dual partnership.

### Color Tokens:
- **Background (`#070a12`):** A deep obsidian slate that reduces eye strain and provides perfect contrast for glows.
- **Panels (`rgba(0, 242, 254, 0.02)`):** Ultra-transparent layers with a heavy blur backdrop to simulate optical holographic glass.
- **Primary Accent (`#00f2fe` - Cortana Cyan):** Used for navigation, active links, neural signals, and Hermes status updates.
- **Secondary Accent (`#39ff14` - DedSec Toxic Green):** Used for database transaction logs, study metrics, and completed streaks.
- **Warning Accent (`#ff007f` - Cyber Pink):** Reserved for alerts, budget overruns, and missed habits.

### Borders & Dividers:
- Containers use a 1px dashed border (`border: 1px dashed rgba(0, 242, 254, 0.25)`).
- Hovering over panels activates a pink/cyan glow: `box-shadow: 0 0 15px rgba(0, 242, 254, 0.2)`.

---

## 3. Typography: HUD Readout
A clean pairing of a geometric display font and a highly legible terminal monospace font.

- **Display Headers (Outfit):** Wide-set, geometric, and uppercase. Slanted style or brackets are used for main headers (e.g. `[ ARCHER_HERMES_LINK ]`).
- **Body & Data Lines (Share Tech Mono / JetBrains Mono):** All list items, numbers, parameters, form labels, and log entries are displayed in monospaced format to resemble system telemetry.

---

## 4. Components

### Navigation Buttons & Tabs:
- Tabs are blocky. Active tabs are fully colored in cyan/green with black text and an outer glow.
- Unfocused tabs have a simple dashed outline and change opacity on hover.

### Stat Cards:
- Framed in dashed borders. Top-right corners contain system tags like `[SYS_DAEMON]` or `[BIO_LINK]`.
- Pulsing glow details in the corner of cards indicate active background syncing.

### Forms & Input Fields:
- Blocky inputs with solid black background and a dashed border. Focus shifts the border to neon pink with a subtle glow.
- Checkboxes are small block squares with custom check indicators.

---

## 5. Screen Transitions: Boot Sequence
- Moving between tabs triggers a 300ms digital "flicker" effect that mimics a hologram rebooting.
- A vertical scanline sweeps across the screen every 6 seconds as a background diagnostic overlay.
