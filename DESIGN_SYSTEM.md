# Communion After Dark — Design System Reference

Sourced from the live site CSS (`site.css`) and banner image inspection.
Goal: make the GTK4 Flatpak player and future Android Jetpack Compose app match this theme.

---

## Color Palette

| Role | Hex | Notes |
|---|---|---|
| Background | `#000000` | Pure black — site and logo background |
| Primary text | `#ffffff` | White — logo "Communion" text |
| Body/subtitle text | `#ababab` | Muted light gray — episode subtitles, secondary text |
| Content text | `#1d1d1d` | Near-black — navigation links, body copy |
| Accent / highlight | `#ff0505` | Bright red — sound wave dots in logo, cart icon, active links |
| Accent (variant) | `#fd1c1c` | Slightly darker red variant — used in some nav elements |
| Hover (nav links) | `rgba(29,29,29,0.9)` | Near-black at 90% opacity, with `transition: color 0.15s ease-out` |
| Hover (dimmed) | `rgba(29,29,29,0.45)` | Near-black at 45% opacity — inactive/dimmed nav state |
| Dark brown | `#3e1811` | From artwork palette — suggested background for image blocks |
| Muted tan | `#b78d7f` | From artwork palette — warm secondary tone |

---

## Typography

### Primary Font: minerva-modern (Adobe Typekit)
- **Source**: `use.typekit.net` — requires Adobe Typekit subscription to self-host
- **Free alternatives**: **Cinzel** (Google Fonts) — classical Roman caps with similar feel; **IM Fell English** for a more gothic tone
- **Usage**: navigation links, headers, site-wide UI text
- **Files available**: Bold, BoldItalic, Black, BlackItalic, Italic (no Regular/400 upright)
- **Weight mapping in app**: Bold → `font-weight: 400` (lightest upright), Black → `font-weight: 700`, BlackItalic → `font-weight: 900`
- **Licensing**: Adobe Fonts — `.ttf` files are gitignored and must be placed locally; not redistributable

### Type Scale (from CSS)

| Usage | Font | Weight | Size | Letter-spacing | Transform |
|---|---|---|---|---|---|
| Navigation links | minerva-modern | 400 | 14px | 0em | uppercase |
| Sub-navigation / tags | minerva-modern | 400 | 12px | 0em | uppercase |
| Cart / UI labels | minerva-modern | 400 | 15px | 0.2em | uppercase |
| Page subtitles | minerva-modern | 400 | 21px | 0em | none |
| Page titles (large) | minerva-modern | 400 | 50px | 0em | none |
| Body / descriptions | minerva-modern | 400 | 15–16px | 0em | none |
| Fallback (all) | `"Helvetica Neue", Arial, sans-serif` | — | — | — | — |

---

## Logo / Banner

- File saved: `public/cad_banner.jpeg` (black background)
- "Communion" — large gothic display letterform with compass/crosshair ornament
- "AFTER DARK" — wide-spaced caps beneath, smaller
- Background: `#000000`
- Logo text: `#ffffff`
- Sound-wave dot matrix: `#ff0505` (red)

---

## Navigation Bar

- Links: `minerva-modern`, 14px, `#1d1d1d`, `text-transform: uppercase`
- Hover: `color: rgba(29,29,29,0.9)`, `transition: color 0.15s ease-out`
- Active/accent items (cart, CTAs): `#ff0505`
- No border / shadow on nav bar itself — flat design
- Nav items spaced with `margin: 0 5px; color: #999` separators

---

## Implementation Notes for GTK4 / Android

- **Dark theme**: use `#000000` or near-black (`#0d0d0d`) as window background
- **Accent color**: `#ff0505` for play button, progress bar fill, active state highlights
- **Text hierarchy**:
  - Episode titles → white (`#ffffff`) or `#ababab`
  - Secondary info (date, duration) → `#ababab` dimmed
  - Body descriptions → `#ababab` or `#b0b0b0`
- **Font substitution for GTK4**: load Cinzel via CSS `@font-face` or use `font-family: 'Cinzel', serif` in the Flatpak CSS provider
- **Font substitution for Android**: include Cinzel in `res/font/`, apply via `TextAppearance` style
- **Pill / badge accent** (e.g. "New!" banner): `#7B2FBE` purple was used in player — could switch to `#ff0505` red to match site branding, or keep purple as a complementary accent
