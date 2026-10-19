# Stitch prompt (original, verbatim)

This is the exact prompt given to Google Stitch to generate the two screens in
`Landing Page/` and `Sign Page/`. Kept as the source of truth for the design brief.
The distilled, enforceable version lives in `../DESIGN.md`.

---

Design two screens for "CodeMap": a Landing page and a Login page (desktop 1440px, plus a mobile layout for each). CodeMap is a privacy-first developer tool that analyzes a Python codebase and shows a dependency map, call graph, dead code, circular dependencies, complexity hotspots, generated docs and an onboarding report. Tagline: "Understand any codebase. Nothing leaves your machine."

DESIGN DIRECTION: quiet, editorial, precise. Think a high-end developer tool (Linear, Vercel, Raycast) crossed with an editorial site. Minimal, but with real personality. Not a generic AI SaaS template.

Look and feel
- Warm off-white paper background #F7F5F0, ink black #0E0E10 text, hairline 1px dividers #E3DFD6
- ONE accent: deep royal violet #4B2BB5, used only for the graph highlights, links on hover, focus rings and one key moment per screen. Optional tiny touch of antique gold #B8923A for a single detail (a small diamond mark, a live-status dot). Nothing else.
- Dark inverted section allowed once on the landing page (ink #0E0E10 background, ivory text) to show the product.
- Typography: huge headlines that mix a LIGHT weight line and a BOLD weight line, like "Understand any" (light) / "codebase." (bold), set in a geometric sans (Geist, Inter Tight or similar). Body text in a refined serif (Newsreader or Source Serif). All code, paths, function names and numbers in JetBrains Mono.
- Square-cornered solid black buttons with small uppercase labels, plus underlined text links with an arrow. 2px radius max.
- Lots of white space, a strict 12-column grid, left-aligned layouts, thin-line icons (1.5px stroke) only.
- AVOID: gradients, glassmorphism, glow, emoji, sparkle icons, stock illustrations, rounded pastel cards, centered everything, drop shadows, fake testimonials, fake logos.

LANDING PAGE (single scroll)
1. Nav: small geometric logo mark (a tiny node-and-edge glyph), links (Features, How it works, Privacy, Docs), right side "Sign in" text link and a black "Analyze a project" button.
2. Hero: huge two-weight headline, one serif sentence beneath, black CTA "Analyze a project" plus a text link "See how it works →". On the right or beneath, a large animated graph of nodes and edges in thin ink lines.
3. Privacy strip: one line in mono, such as "$ codemap analyze ./my-project   → parsed locally · 0 bytes uploaded", with a small gold status dot.
4. "Start reading any codebase." Three columns with thin icons: Parse (AST only, your code is never executed), Map (graph of modules, classes, calls), Understand (docs and an onboarding report). Serif body copy.
5. Feature showcase: a dark section with an interactive-looking product window (a dependency graph with a side panel showing a selected node, its file path in mono, and "blast radius: 14"). A circular dependency is highlighted in violet with a note "Suggested edge to remove".
6. Six compact feature rows divided by hairlines: Dependency map, Call graph, Dead code, Circular dependencies, Complexity hotspots, Onboarding report. Each has a one-line description and a tiny mono example.
7. Two modes side by side: Local (no login, one launcher file, SQLite) and Cloud (login, zip upload, history). Optional AI explanations are shown as OFF by default.
8. Final CTA: large light/bold headline "Read the code. Keep it private." with the black button.
9. Footer: logo, "Team CoCreate · MES IMCC", links in muted serif, small uppercase legal links.

LOGIN PAGE
- Split layout. Left 45%: the form on paper background. Right 55%: ink-black panel with a slowly animated graph and one quiet line in mono, "Your code never leaves your machine."
- Form: logo, headline "Welcome back." (light) / "Sign in." (bold), email and password with underline-style inputs (no boxes), a show/hide toggle, a black "Sign in" button, "Create account" link, "Forgot password" link.
- Below a hairline divider: "Prefer to stay offline? Continue in local mode, no login →" as a secondary outlined button.
- Include states: focus (violet underline), error (inline message in mono), loading (button text becomes a progress line), and a Register variant.

ANIMATION (specify these in the design and prototype)
- Hero graph: nodes fade in one by one, edges draw along their path (stroke-dashoffset), then one cycle edge turns violet and pulses once. After that, nodes drift very slowly. Hovering a node highlights its neighbors and dims the rest.
- Headline: the light line fades up first, then the bold line reveals with a clean masked slide-up (about 600ms, ease-out cubic).
- Scroll reveals: sections fade up 16px with a 60ms stagger. Hairlines draw from left to right as they enter.
- The terminal line in the privacy strip types out once, then a blinking cursor.
- Dark product window: when scrolled into view, the graph assembles, the node gets selected, and the side panel slides in with the blast radius count ticking up.
- Buttons: the black button gets a subtle arrow slide on hover. Text links get an underline that grows from the left.
- Login: the right-hand graph moves slowly, and inputs show an underline that expands on focus.
- Respect prefers-reduced-motion (show the final static state). Nothing loops faster than 8 seconds per cycle, and nothing should feel flashy.

Add a small tweaks panel with: accent color picker, a headline weight slider, a motion on/off toggle and a dark/light toggle. Keep all components consistent (buttons, inputs, links, section headers) so they can be reused across the rest of the app.
