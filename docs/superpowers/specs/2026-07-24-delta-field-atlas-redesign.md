# Delta Field Atlas redesign

**Date:** 2026-07-24  
**Status:** Approved direction  
**Owner:** Sefayet / Codex

## Objective

Redesign the full AgriSense frontend as a distinctive, professional,
Bangladesh-agriculture product while preserving every current function, API
contract, route, validation rule, streaming behavior, billing flow and password
flow. The application remains light-only.

## Visual direction

“Delta Field Atlas” combines Bangladesh’s agricultural landscape with the
clarity of a field surveyor’s notebook:

- Warm rice-paper canvas rather than sterile white.
- Paddy green as the primary signal color.
- Jute beige and sun-baked terracotta as supporting colors.
- A restrained river-blue color only for weather and water information.
- Fine contour lines, irrigation paths, plot boundaries and grain textures.
- Asymmetric editorial compositions instead of equal card grids.
- Authentic Bangladesh field photography presented as layered landscape plates.
- Confident, specific copy without AI-product clichés.

There is no dark mode and no dark marketing section.

## Brand system

Create a new custom AgriSense mark built from three ideas:

1. A rice panicle.
2. A river-delta path.
3. A surveyed field boundary.

The mark must remain legible at favicon size. The same geometry drives:

- Main logo and wordmark.
- Compact workspace/profile mark.
- Browser favicon.
- Decorative line motifs.

Typography uses a characterful editorial display face paired with a highly
readable humanist sans and a tabular mono face for figures. Large headlines use
tight tracking and balanced wrapping. Labels use sentence case rather than
generic all-caps pills.

## Home page

The home page becomes a scroll-led field story.

### Hero

- Split, asymmetric layout with copy on the left and an interactive field
  landscape on the right.
- React Three Fiber renders a lightweight 2.5D/3D delta landscape made from
  layered field plots, irrigation channels, crop markers and a moving sun.
- Pointer movement produces subtle camera parallax.
- Animation pauses when the tab is hidden and respects reduced-motion.
- A CSS/SVG fallback appears if WebGL is unavailable.
- Primary actions keep their existing destinations and authentication behavior.

### Scroll narrative

GSAP ScrollTrigger powers:

- Cropped mask reveals for field photography.
- Draw-on route/irrigation lines.
- Staggered text and data entries.
- A pinned “field to plan” sequence on desktop.
- Natural vertical reveals on mobile.

Only transforms and opacity are animated. Motion is disabled or simplified for
`prefers-reduced-motion`.

### Content structure

- Field-note introduction with real product outcomes.
- Four capabilities arranged as an offset route rather than equal cards.
- A weather-to-crop-to-calendar-to-profit process sequence.
- Bangladesh farmer stories in an editorial masonry composition.
- Final invitation integrated over a light agricultural photograph.
- Image credits link to each source/license.

Photography comes from properly licensed Bangladesh agriculture sources,
preferably Wikimedia Commons. Initial selected source collections:

- `Category:Paddy fields in Bangladesh`
- `Category:Agriculture in Bangladesh`
- `Category:Farmers from Bangladesh`

Assets are downloaded into `frontend/public/images/` so the demo does not rely
on external hotlinks. Every meaningful image has descriptive alt text.

## Application pages

### Authentication

Login, registration and password recovery use a shared light “field station”
shell:

- Editorial brand panel with Bangladesh field imagery.
- Form panel with strong hierarchy and accessible validation.
- Existing form state, redirects, phone normalization, OTP and API calls remain
  unchanged.

### Chat workspace

The workspace becomes a calm agronomic desk:

- Textured warm canvas and plot-line pattern.
- More purposeful sidebar hierarchy.
- Messages read as field notes rather than generic chat bubbles.
- Tool trace and plan artifacts look like survey records.
- Composer remains continuously available.
- Streaming, session persistence, trace toggles, attachments and navigation
  behavior remain unchanged.

### Profile

Profile becomes a field account ledger:

- Identity and farm location at the top.
- Tabs remain Info, History and Billing.
- Active tab is stored in the URL as `?tab=info|history|billing`.
- Selecting a tab updates the URL without reloading.
- Browser refresh restores the exact selected tab.
- Invalid/missing tab values fall back to `info`.
- Password change, subscription activation/cancellation and real session
  history retain their existing API behavior.

### Demo and errors

- `/demo` adopts the same workspace shell and tokens.
- Add a branded not-found screen with a route back home.
- Loading, empty and error states use the same visual language.

## Component and styling architecture

- Preserve Next.js App Router, React, Tailwind and current data/API layers.
- Add GSAP, ScrollTrigger, React Three Fiber and Three.js only where needed.
- Isolate the hero scene so WebGL code never enters chat/profile bundles.
- Create reusable brand, page-shell, reveal and surface primitives.
- Update semantic Tailwind tokens rather than scattering arbitrary colors.
- Remove obsolete reveal/parallax code after the new motion system is live.
- Do not change backend endpoints, response shapes or business logic.

## Functional invariants

The redesign must not alter:

- Authentication and token refresh behavior.
- Registration address selection and validation.
- Forgot-password OTP flow.
- Authenticated password change.
- Chat streaming and cross-navigation persistence.
- Session selection/deletion and history loading.
- Tool-trace visibility and raw result access.
- Plan-card calculations and rendering.
- Billing plan loading, OTP verification, activation and cancellation.
- `/demo` behavior.
- All existing links and redirects unless explicitly replaced by an equivalent
  persistent profile-tab URL.

## Performance and accessibility

- Lazy-load the R3F hero and render it only on the home page.
- Cap WebGL DPR and avoid per-frame React state updates.
- Use GSAP contexts and destroy ScrollTriggers on unmount.
- Stop nonessential animation offscreen.
- Preserve visible focus states and keyboard navigation.
- Provide a skip link and semantic landmarks.
- Meet readable contrast on every light surface.
- Avoid layout shift by reserving image and scene dimensions.

## Verification

Before completion:

1. `npm run typecheck`
2. `npm run build`
3. Full backend test suite
4. Docker rebuild and health check
5. Manual route/interaction pass for home, login, register, forgot password,
   chat, profile Info/History/Billing and demo
6. Refresh each profile tab and confirm it persists
7. Verify reduced-motion and responsive fallbacks
8. Check the favicon and logo at compact sizes
9. Confirm `git diff --check`
10. Fetch and merge the latest `origin/main`, resolve conflicts, then push only
    `feat/agrisense-workspace`

## Scope exclusions

- No backend contract changes.
- No dark theme.
- No new product features unrelated to presentation or profile-tab persistence.
- No animation that blocks interaction or delays important content.
- No unlicensed or unattributed photography.
