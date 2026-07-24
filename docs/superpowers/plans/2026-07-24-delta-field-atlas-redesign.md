# Delta Field Atlas Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign every AgriSense frontend route as a distinctive, light-only Bangladesh agricultural field atlas while preserving every existing authentication, chat, planning, profile, billing, and password function.

**Architecture:** Keep the current Next.js App Router, React state providers, API client, and Tailwind component structure. Add a small reusable visual foundation, GSAP reveal primitives, and one dynamically loaded React Three Fiber hero scene with a no-WebGL fallback; route pages remain responsible for their current data and mutation behavior. Persist the profile tab in the URL query string so direct links and refreshes restore the same subsection.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, GSAP with ScrollTrigger, React Three Fiber, Three.js, Lucide React, TanStack Query

## Global Constraints

- Preserve every currently working function and API contract.
- Use only a light visual theme; do not add dark-mode variants.
- Keep the existing Next.js + React + Tailwind architecture and current backend endpoints.
- Use Bangladesh agriculture imagery with locally stored, licensed assets and recorded attribution.
- Keep WebGL isolated to the home hero and load it dynamically without server-side rendering.
- Honor `prefers-reduced-motion`, keyboard navigation, and visible focus states.
- Never push to `main`; commit and push only `feat/agrisense-workspace`.
- Update `HANDOFF.md` Section 5, `PLAN.md`, and `frontend/CLAUDE_frontend.md` before completion.

---

## File Structure

**Create**

- `frontend/src/components/home/FieldAtlasScene.tsx` — isolated React Three Fiber hero landscape.
- `frontend/src/components/home/FieldAtlasFallback.tsx` — SVG/CSS fallback and reduced-motion hero art.
- `frontend/src/components/layout/AuthShell.tsx` — shared branded layout for login, registration, and password recovery.
- `frontend/src/components/ui/SectionHeading.tsx` — consistent eyebrow/title/supporting-copy composition.
- `frontend/src/lib/motion.ts` — GSAP registration and reduced-motion helpers.
- `frontend/src/app/not-found.tsx` — branded missing-route experience.
- `frontend/public/images/paddy-reflection-bangladesh.jpg` — locally stored hero/supporting photo.
- `frontend/public/images/paddy-landscape-bangladesh.jpg` — locally stored editorial photo.
- `frontend/public/images/IMAGE_CREDITS.md` — source, author, and license details.

**Modify**

- `frontend/package.json`, `frontend/package-lock.json` — motion and 3D dependencies.
- `frontend/tailwind.config.ts`, `frontend/src/app/globals.css` — field-atlas tokens, texture, typography, focus, motion, and reusable utilities.
- `frontend/src/app/layout.tsx`, `frontend/public/favicon.svg` — metadata, fonts, favicon, and global shell.
- `frontend/src/components/ui/Logo.tsx`, `frontend/src/components/ui/LeafMark.tsx` — unified delta-field brand geometry.
- `frontend/src/components/home/Reveal.tsx`, `frontend/src/app/page.tsx` — GSAP reveal behavior and complete home composition.
- `frontend/src/app/login/page.tsx`, `frontend/src/app/register/page.tsx`, `frontend/src/app/forgot-password/page.tsx` — shared auth shell without changing handlers.
- `frontend/src/components/ui/TextInput.tsx`, `frontend/src/components/ui/PasswordInput.tsx`, `frontend/src/components/ui/Select.tsx`, `frontend/src/components/address/AddressPicker.tsx` — shared form styling.
- `frontend/src/app/chat/page.tsx`, `frontend/src/components/workspace/WorkspaceShell.tsx`, `frontend/src/components/chat/*.tsx`, `frontend/src/components/trace/TracePanel.tsx`, `frontend/src/components/plan/*.tsx` — agronomic desk styling while retaining data flow.
- `frontend/src/app/profile/page.tsx`, `frontend/src/components/profile/PieChart.tsx`, `frontend/src/components/billing/BdAppsCheckout.tsx` — URL-persistent profile tabs and redesigned account surfaces.
- `frontend/src/app/demo/page.tsx` — field-notebook demonstration styling.
- `HANDOFF.md`, `PLAN.md`, `frontend/CLAUDE_frontend.md` — implementation handoff state.

---

### Task 1: Install the Visual Runtime and Establish Brand Foundations

**Files:**

- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/components/ui/Logo.tsx`
- Modify: `frontend/src/components/ui/LeafMark.tsx`
- Modify: `frontend/public/favicon.svg`
- Create: `frontend/src/components/ui/SectionHeading.tsx`

**Interfaces:**

- Produces: `Logo({ compact?: boolean; className?: string })`, `LogoMark({ className?: string })`, and `SectionHeading({ eyebrow, title, description, align? })`.
- Produces: Tailwind colors `paper`, `field`, `jute`, `clay`, `river`, and shared classes `atlas-panel`, `atlas-grid`, `atlas-focus`.

- [ ] **Step 1: Record the clean baseline**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: both commands exit with code 0 before visual changes.

- [ ] **Step 2: Install the bounded animation dependencies**

Run:

```bash
cd frontend
npm install gsap @gsap/react three @react-three/fiber
npm install --save-dev @types/three
```

Expected: `package.json` contains the four runtime packages and `@types/three`; the lockfile changes without unrelated dependency replacement.

- [ ] **Step 3: Define the light field-atlas tokens**

Implement this token shape in `tailwind.config.ts` and mirror the values as CSS variables in `globals.css`:

```ts
colors: {
  paper: { 50: "#fffdf6", 100: "#f7f1df", 200: "#e9ddbd" },
  field: { 500: "#3f6f35", 600: "#315c2b", 700: "#254a24", 900: "#17351b" },
  jute: { 300: "#d9c28f", 500: "#ab8b50" },
  clay: { 400: "#c96f42", 500: "#ad5835" },
  river: { 300: "#7fb6bf", 500: "#43838d" },
  ink: { 700: "#344338", 900: "#17261c" },
}
```

Add paper grain, field-line utilities, strong `:focus-visible` rings, text selection colors, and a `prefers-reduced-motion` block that disables nonessential transforms and smooth scrolling.

- [ ] **Step 4: Replace the brand geometry**

Build a single SVG identity used by `LogoMark`, `Logo`, and `favicon.svg`: a rounded field boundary containing a river-delta path and three rice grains. Keep the mark legible at 16×16 and use `currentColor` in React components.

```tsx
export function LogoMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden="true">
      <path d="M8 7h32v34H8z" fill="none" stroke="currentColor" strokeWidth="3" rx="10" />
      <path d="M24 9c0 13-8 15-8 29M24 17c4 8 9 11 15 13" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <path d="M16 15c4-3 7-3 10 0M29 23c4-2 7-1 9 2" fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
```

Adjust the exact paths during implementation only to improve optical balance; keep the field, delta, and rice semantics unchanged.

- [ ] **Step 5: Update metadata and validate**

Set the title template to `%s · AgriSense`, describe AgriSense as a Bangladesh-focused crop planning workspace, retain the SVG icon, and run:

```bash
cd frontend
npm run typecheck
git diff --check
```

Expected: no TypeScript errors or whitespace errors.

- [ ] **Step 6: Commit the foundation**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tailwind.config.ts frontend/src/app/globals.css frontend/src/app/layout.tsx frontend/src/components/ui/Logo.tsx frontend/src/components/ui/LeafMark.tsx frontend/src/components/ui/SectionHeading.tsx frontend/public/favicon.svg
git commit -m "feat: establish Delta Field Atlas design system"
```

---

### Task 2: Add Motion Primitives and the 2.5D Field Scene

**Files:**

- Create: `frontend/src/lib/motion.ts`
- Modify: `frontend/src/components/home/Reveal.tsx`
- Create: `frontend/src/components/home/FieldAtlasScene.tsx`
- Create: `frontend/src/components/home/FieldAtlasFallback.tsx`

**Interfaces:**

- Produces: `registerGsap(): void` and `motionAllowed(): boolean`.
- Produces: `Reveal({ children, className?, delay?, y? })`.
- Produces: default `FieldAtlasScene` component with no props and named `FieldAtlasFallback`.

- [ ] **Step 1: Centralize motion policy**

Implement browser-safe registration and a reduced-motion query:

```ts
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

export function registerGsap() {
  if (typeof window !== "undefined") gsap.registerPlugin(ScrollTrigger);
}

export function motionAllowed() {
  return typeof window !== "undefined"
    && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
```

- [ ] **Step 2: Replace viewport-observer reveals with GSAP context cleanup**

Use `useGSAP` scoped to a wrapper ref; animate opacity and y only when motion is allowed and return immediately visible content otherwise.

```tsx
useGSAP(() => {
  if (!motionAllowed() || !root.current) return;
  gsap.fromTo(root.current, { autoAlpha: 0, y }, {
    autoAlpha: 1,
    y: 0,
    delay,
    duration: 0.72,
    ease: "power3.out",
    scrollTrigger: { trigger: root.current, start: "top 88%", once: true },
  });
}, { scope: root });
```

- [ ] **Step 3: Build the static fallback first**

Create an accessible decorative field map with layered SVG paths, terraced plots, river curves, a sun disc, and subtle CSS transforms. Mark it `aria-hidden="true"` and keep all information duplicated in the hero text.

- [ ] **Step 4: Build the isolated React Three Fiber scene**

Render low-poly field planes, a curved river strip, rice-stalk instancing, orthographic camera, ambient/directional light, and pointer-driven camera easing. Cap device pixel ratio and avoid shadows:

```tsx
<Canvas
  dpr={[1, 1.5]}
  orthographic
  camera={{ position: [5, 6, 7], zoom: 72 }}
  gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
>
  <ambientLight intensity={1.7} />
  <directionalLight position={[4, 8, 6]} intensity={2.1} />
  <FieldLandscape />
</Canvas>
```

Use `useFrame` only for camera easing and rice sway; invalidate continuously only while motion is enabled.

- [ ] **Step 5: Verify isolation and cleanup**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: the build succeeds, the home route owns a separate client chunk containing Three.js, and no `window is not defined` error appears.

- [ ] **Step 6: Commit the motion layer**

```bash
git add frontend/src/lib/motion.ts frontend/src/components/home/Reveal.tsx frontend/src/components/home/FieldAtlasScene.tsx frontend/src/components/home/FieldAtlasFallback.tsx
git commit -m "feat: add field atlas motion system"
```

---

### Task 3: Recompose the Home Page Around Bangladesh Agriculture

**Files:**

- Modify: `frontend/src/app/page.tsx`
- Create: `frontend/public/images/paddy-reflection-bangladesh.jpg`
- Create: `frontend/public/images/paddy-landscape-bangladesh.jpg`
- Create: `frontend/public/images/IMAGE_CREDITS.md`

**Interfaces:**

- Consumes: dynamically imported `FieldAtlasScene`, `FieldAtlasFallback`, `Reveal`, `Logo`, and `SectionHeading`.
- Preserves: existing navigation targets for account creation, login, demo, chat, and profile.

- [ ] **Step 1: Download and document licensed imagery**

Use the Wikimedia Commons originals for “Paddy Field Reflection in Rural Bangladesh” by A S M Jobaer and “Landscape of Paddy crop in Bangladesh” by Wiki Ruhan. Save optimized local JPEGs and record the source page, author, CC BY-SA 4.0 license, and retrieval date in `IMAGE_CREDITS.md`.

Validate:

```bash
file frontend/public/images/*.jpg
du -h frontend/public/images/*.jpg
```

Expected: valid JPEG files, each below 700 KB after optimization.

- [ ] **Step 2: Build the asymmetric hero**

Use a left editorial column and right atlas viewport. Load WebGL only in the browser:

```tsx
const FieldAtlasScene = dynamic(
  () => import("@/components/home/FieldAtlasScene"),
  { ssr: false, loading: () => <FieldAtlasFallback /> },
);
```

Keep concise human copy: “Plan the season before the soil pays for it.” Provide the primary action “Build a crop plan” and secondary action “Explore the demo.”

- [ ] **Step 3: Replace equal-card sections**

Compose a field-notes ribbon, an offset three-step planning sequence, one full-width photographic proof section, a compact capability index, and a final call-to-action. Avoid repeated rounded cards and generic claims; tie copy to crop choice, local prices, seasonal timing, and cost visibility.

- [ ] **Step 4: Add scroll choreography**

Pin only the planning-sequence illustration on desktop, reveal map lines with `strokeDashoffset`, and shift image layers by no more than 6% of their height. On screens below 768px and reduced-motion environments, render the natural document flow with no pinning.

- [ ] **Step 5: Verify the route**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- `/` renders without WebGL before hydration errors.
- Every call-to-action reaches its prior route.
- Keyboard focus follows visual reading order.
- At 360px width no horizontal scrolling occurs.

- [ ] **Step 6: Commit the home page**

```bash
git add frontend/src/app/page.tsx frontend/public/images
git commit -m "feat: redesign home as a living field atlas"
```

---

### Task 4: Unify Authentication and Form Surfaces

**Files:**

- Create: `frontend/src/components/layout/AuthShell.tsx`
- Modify: `frontend/src/app/login/page.tsx`
- Modify: `frontend/src/app/register/page.tsx`
- Modify: `frontend/src/app/forgot-password/page.tsx`
- Modify: `frontend/src/components/ui/TextInput.tsx`
- Modify: `frontend/src/components/ui/PasswordInput.tsx`
- Modify: `frontend/src/components/ui/Select.tsx`
- Modify: `frontend/src/components/address/AddressPicker.tsx`

**Interfaces:**

- Produces: `AuthShell({ eyebrow, title, description, children, aside })`.
- Preserves: login submission, registration address selection, fixed mock OTP `1234`, password reset request/confirmation, validation, redirects, and error messaging.

- [ ] **Step 1: Create the field-station auth shell**

Implement a two-column shell with a concise route-specific intro, field-map decoration, logo link, and a focused form well:

```tsx
type AuthShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
  aside: React.ReactNode;
};
```

Collapse to a single column below `lg`; the form content must appear first in the DOM.

- [ ] **Step 2: Restyle shared controls without changing their contracts**

Retain all prop signatures and ref behavior. Apply 44px minimum control height, persistent labels, `aria-invalid`, clay error text, field-green focus rings, and paper backgrounds.

- [ ] **Step 3: Move each auth page into `AuthShell`**

Keep existing state, mutation calls, and navigation code byte-for-byte where practical. Change headings and support copy only. Ensure registration retains its “Forgot password?” entry point and that password recovery still clearly states the development OTP is `1234`.

- [ ] **Step 4: Verify auth behavior**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- Invalid login displays the server message.
- Registration retains address and phone validation.
- Forgot-password request advances to OTP confirmation.
- OTP `1234` and a valid new password complete reset.
- Password visibility buttons remain keyboard accessible.

- [ ] **Step 5: Commit authentication styling**

```bash
git add frontend/src/components/layout/AuthShell.tsx frontend/src/app/login/page.tsx frontend/src/app/register/page.tsx frontend/src/app/forgot-password/page.tsx frontend/src/components/ui/TextInput.tsx frontend/src/components/ui/PasswordInput.tsx frontend/src/components/ui/Select.tsx frontend/src/components/address/AddressPicker.tsx
git commit -m "feat: redesign authentication field station"
```

---

### Task 5: Redesign the Chat, Trace, and Plan Workspace

**Files:**

- Modify: `frontend/src/app/chat/page.tsx`
- Modify: `frontend/src/components/workspace/WorkspaceShell.tsx`
- Modify: `frontend/src/components/chat/ChatColumn.tsx`
- Modify: `frontend/src/components/chat/Composer.tsx`
- Modify: `frontend/src/components/chat/EmptyState.tsx`
- Modify: `frontend/src/components/chat/Markdown.tsx`
- Modify: `frontend/src/components/chat/MessageBubble.tsx`
- Modify: `frontend/src/components/chat/Sidebar.tsx`
- Modify: `frontend/src/components/chat/StatusPill.tsx`
- Modify: `frontend/src/components/chat/ToolTraceChips.tsx`
- Modify: `frontend/src/components/trace/TracePanel.tsx`
- Modify: `frontend/src/components/plan/CropComparison.tsx`
- Modify: `frontend/src/components/plan/FinanceChart.tsx`
- Modify: `frontend/src/components/plan/PlanCard.tsx`
- Modify: `frontend/src/components/plan/SeasonCalendar.tsx`

**Interfaces:**

- Preserves: `ChatProvider`, conversation lifecycle, message streaming, attachments, stop/retry, trace inspection, sidebar operations, saved-plan display, and every plan visualization input.
- Produces: a responsive agronomic desk with conversation rail, working ledger, and trace drawer.

- [ ] **Step 1: Restyle the workspace shell**

Keep the existing providers and responsive state. Replace the generic app chrome with a field-green masthead, paper workspace, atlas dividers, and clearly differentiated navigation, content, and inspection regions.

- [ ] **Step 2: Restyle the conversation flow**

Keep every callback and data selector. Use restrained message grouping, a solid farmer message block, an editorial assistant response, a bottom-anchored composer, and visible stream/stop states. Preserve semantic buttons and labels.

- [ ] **Step 3: Restyle trace and status details**

Present tool traces as expandable field-record entries, keep raw trace visibility, and use status colors that are distinguishable by icon and label as well as color.

- [ ] **Step 4: Restyle plan artifacts**

Use ledger rows, crop tags, ruled calendars, and labeled charts. Preserve calculation inputs and numeric formatting; do not alter finance formulas or plan parsing.

- [ ] **Step 5: Verify workspace functionality**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- Create, select, rename, and delete a conversation.
- Send a text message and an attachment.
- Stop an in-progress response and retry a failed message.
- Open and close trace details.
- Render crop comparison, finance, calendar, and plan cards on desktop and mobile.

- [ ] **Step 6: Commit the workspace redesign**

```bash
git add frontend/src/app/chat/page.tsx frontend/src/components/workspace frontend/src/components/chat frontend/src/components/trace frontend/src/components/plan
git commit -m "feat: redesign agronomic planning workspace"
```

---

### Task 6: Persist Profile Tabs and Redesign Account/Billing

**Files:**

- Modify: `frontend/src/app/profile/page.tsx`
- Modify: `frontend/src/components/profile/PieChart.tsx`
- Modify: `frontend/src/components/billing/BdAppsCheckout.tsx`

**Interfaces:**

- Produces: `type ProfileTab = "info" | "history" | "billing"` and `parseProfileTab(value: string | null): ProfileTab`.
- Preserves: personal-information update, password update, history rendering, billing plan selection, OTP request/confirmation, subscription refresh, cancellation, and mock OTP `1234`.

- [ ] **Step 1: Add a deterministic URL-tab parser**

Implement:

```ts
type ProfileTab = "info" | "history" | "billing";

function parseProfileTab(value: string | null): ProfileTab {
  return value === "history" || value === "billing" ? value : "info";
}
```

Read `useSearchParams()` for initial/current state and use `router.replace()` when a tab changes:

```tsx
const activeTab = parseProfileTab(searchParams.get("tab"));

function selectTab(tab: ProfileTab) {
  const query = new URLSearchParams(searchParams.toString());
  query.set("tab", tab);
  router.replace(`/profile?${query.toString()}`, { scroll: false });
}
```

- [ ] **Step 2: Replace the profile chrome**

Use a field-ledger header and route-aware tab links/buttons. Keep all forms mounted according to the active tab exactly as before and retain loading, success, and error states.

- [ ] **Step 3: Restyle personal information and password update**

Separate identity and security as two editorial sections. Do not change update payloads, current-password requirements, query invalidation, or form reset behavior.

- [ ] **Step 4: Restyle history and billing**

Convert history to a readable season ledger, update `PieChart` colors to the field palette, and style `BdAppsCheckout` as a clear three-stage subscription flow. Keep backend-derived status authoritative and label the development OTP as `1234`.

- [ ] **Step 5: Verify refresh persistence and mutations**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Manual checks:

- `/profile?tab=history` refreshes on History.
- `/profile?tab=billing` refreshes on Billing.
- `/profile?tab=unknown` renders Personal info.
- Back/forward navigation follows tab history semantics created by `replace`.
- Profile update and password update still submit successfully.
- Billing request, OTP confirmation with `1234`, status refresh, and cancellation still work.

- [ ] **Step 6: Commit account improvements**

```bash
git add frontend/src/app/profile/page.tsx frontend/src/components/profile/PieChart.tsx frontend/src/components/billing/BdAppsCheckout.tsx
git commit -m "feat: redesign profile and persist active tab"
```

---

### Task 7: Finish Secondary Routes and Perform Visual Hardening

**Files:**

- Modify: `frontend/src/app/demo/page.tsx`
- Create: `frontend/src/app/not-found.tsx`
- Modify: any frontend file from Tasks 1–6 that fails responsive, accessibility, or visual inspection.

**Interfaces:**

- Preserves: demo controls, scenario steps, reset behavior, route links, and all existing user-facing states.
- Produces: consistent empty, loading, error, success, and missing-route states.

- [ ] **Step 1: Redesign the demo as a guided field notebook**

Keep the existing scenario state machine and handlers. Present the sequence as numbered field observations with a sticky progress index on desktop and a compact progress strip on mobile.

- [ ] **Step 2: Add the branded missing-route page**

Create a server-safe page using `LogoMark`, one sentence of plain language, and links to `/` and `/chat`:

```tsx
export default function NotFound() {
  return (
    <main className="atlas-grid grid min-h-screen place-items-center px-6">
      <section className="atlas-panel max-w-xl p-10 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-clay-500">Field marker 404</p>
        <h1 className="mt-4 font-display text-4xl text-ink-900">This path leaves the mapped field.</h1>
      </section>
    </main>
  );
}
```

Include the two route links in the final implementation.

- [ ] **Step 3: Inspect all routes at responsive widths**

Check `/`, `/login`, `/register`, `/forgot-password`, `/chat`, `/profile?tab=info`, `/profile?tab=history`, `/profile?tab=billing`, `/demo`, and a missing route at 360×800, 768×1024, and 1440×900.

Expected: no clipped controls, overlapping text, inaccessible navigation, horizontal overflow, or unreadable contrast.

- [ ] **Step 4: Audit motion and interaction**

Enable reduced motion at the OS/browser level and verify the home remains complete, the R3F scene falls back or stays still, reveal content remains visible, and focus is never moved by animation.

- [ ] **Step 5: Commit secondary-route polish**

```bash
git add frontend/src/app/demo/page.tsx frontend/src/app/not-found.tsx frontend
git commit -m "feat: complete field atlas route redesign"
```

---

### Task 8: Regression Verification, Handoff, Main Sync, and Feature-Branch Push

**Files:**

- Modify: `HANDOFF.md`
- Modify: `PLAN.md`
- Modify: `frontend/CLAUDE_frontend.md`

**Interfaces:**

- Consumes: all completed frontend behavior and the existing backend test suite.
- Produces: verified feature branch and current handoff documentation.

- [ ] **Step 1: Run frontend static verification**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: both commands exit 0 and every App Router page builds.

- [ ] **Step 2: Run backend regression verification**

```bash
docker compose exec -T backend pytest -q
```

Expected: all existing backend tests pass, including authentication, password, and billing tests.

- [ ] **Step 3: Run repository hygiene checks**

```bash
git diff --check
git status --short
git log --oneline --decorate -12
```

Expected: no whitespace errors, no generated build artifacts, and only intentional source/documentation changes.

- [ ] **Step 4: Update continuity documents**

Record the completed redesign, dependency additions, photo attribution location, profile URL-tab contract, verification commands/results, decisions, and remaining blockers in `HANDOFF.md` Section 5, `PLAN.md`, and `frontend/CLAUDE_frontend.md`. End the handoff section with:

```text
Last updated by: Codex.
```

- [ ] **Step 5: Commit verification documentation**

```bash
git add HANDOFF.md PLAN.md frontend/CLAUDE_frontend.md
git commit -m "docs: record Delta Field Atlas completion"
```

- [ ] **Step 6: Re-fetch and merge main**

```bash
git fetch origin main
git merge origin/main
```

Expected: fast-forward or a clean merge. If conflicts occur, resolve only after comparing both sides and rerun Steps 1–3.

- [ ] **Step 7: Push only the current feature branch**

Confirm:

```bash
git branch --show-current
```

Expected: `feat/agrisense-workspace`.

Push:

```bash
git push origin feat/agrisense-workspace
```

Expected: remote branch updates successfully; `main` is untouched.

