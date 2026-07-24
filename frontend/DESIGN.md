# DESIGN.md — AgriSense "Agronomic Instrument" (B3)

The locked art direction for the AgriSense frontend. Every UI decision matches this
file. Informed by `ui-ux-pro-max` (Dark-OLED operations pattern) + the product goal:
make the **agent's reasoning and real tool-calls legible to a judge in 4 minutes**.

> Anti-slop rule: this is **not** a ChatGPT/Claude clone. Same familiar chat
> ergonomics, but a distinct **field-instrument** skin — dark soil canvas, phosphor
> signal-green, monospace telemetry, a topographic background. If it looks like the
> default assistant UI, it's wrong.

## Named aesthetic
**Agronomic Instrument** — a mission-control panel for a farm. Deep soil-dark canvas,
data rendered like live telemetry, the agent trace reads as an instrument readout.
Warm enough to trust (it advises farmers), precise enough to prove (it convinces judges).

## Type system (real fonts, Google-hosted, `display: swap`)
- **Display / headings:** `Space Grotesk` (600/700) — technical but characterful; the identity voice.
- **Body / UI:** `Inter` (400/500/600) — workhorse legibility for chat + forms.
- **Mono / data / trace:** `JetBrains Mono` (400/500/700) — tool-calls, geocodes, timings,
  currency and all tabular numbers. Uses `font-variant-numeric: tabular-nums` so figures never jitter.

Scale (rem): 0.75 · 0.8125 · 0.875 · 1 · 1.125 · 1.25 · 1.5 · 2 · 2.5 · 3.25. Body 16px, line-height 1.5–1.6.

## Color palette (dark-only, semantic tokens)
| Role | Hex | Note |
|---|---|---|
| `canvas` (bg) | `#0B0F0C` | near-black with a green-warm undertone (not pure #000) |
| `surface` | `#12181B`→`#141A16` | raised panels |
| `surface-2` | `#1A221C` | elevated cards, trace rows |
| `border` | `#2A342B` | hairlines |
| `text` | `#E8EFE6` | warm off-white (AAA on canvas) |
| `text-muted` | `#8A968A` | secondary |
| `signal` (primary) | `#34D399` | phosphor agronomy green — live/active, primary CTA |
| `signal-glow` | `#7CF5A3` | glow accents on the newest tool-call only |
| `amber` (accent) | `#F5A524` | highlights, warnings, "attention" (WCAG-tuned) |
| `danger` | `#F0533D` | errors, destructive |
| `viz` sequence | `#34D399 · #2DD4BF · #F5A524 · #E9795B` | charts |

Functional color is never the only signal — pair with icon/text. Contrast ≥4.5:1 body, ≥3:1 large/glyphs.

## Spacing & layout
- 4px base rhythm (4/8/12/16/24/32/48/64). Container `max-w-[1400px]`.
- **Workspace (desktop-first, the demo surface):** `Sidebar 280` │ `Chat (fluid)` │ `Trace panel 340 (collapsible → 0)`.
- Radius scale 6/10/14/20. Elevation via subtle border + low-emission shadow (dark mode: shadow is faint, depth comes from surface-tone steps).
- Responsive down to 768px (trace panel becomes a toggled overlay); 375px readable fallback for the "what the farmer sees" narrative.

## Motion language
- Micro-interactions 150–240ms, `ease-out` enter / ~60% faster exit. `transform`/`opacity` only.
- **Trace:** new tool-call rows stream in with a 30–40ms stagger + a one-shot phosphor `signal-glow` pulse on the **newest** call (this is how "latest vs history" reads).
- **Finance:** numbers count-up ~250ms on recompute (tabular-nums, no layout shift).
- Everything obeys `prefers-reduced-motion`: no glow, no count-up, no terrain animation — instant, fully readable.

## The ONE hero 2.5D/3D moment (deliberate scope)
**Landing/auth only:** a slowly rotating low-poly **contour terrain** (a stylized field/AEZ mesh) with a
soft light sweep — the "instrument booting up." Built with R3F (`r3f-fundamentals` + lighting; loaders only
if a mesh asset is used). Lazy-loaded (dynamic import), **landing-only**. Reduced-motion → a static render.
**Everything else is clean 2.5D:** layered surfaces, soft depth, GSAP/Framer used sparingly. No full-3D
inside the workspace — legibility and 60fps win at a live final.

## Performance & accessibility intent (up front)
- 60fps target; heavy/3D code split out of the workspace bundle. Fonts `display: swap`, reserve space (no CLS).
- `prefers-reduced-motion` respected globally. Keyboard nav + visible focus rings (2px `signal`). Trace/artifacts reachable by keyboard.
- Dark-only, but every fg/bg pair verified ≥4.5:1. Tabular numerics for all data. Icons = Lucide (SVG), never emoji.
