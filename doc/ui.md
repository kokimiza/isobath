---
name: '人格海図 ISOBATH'
description: '明るいお風呂の中に深海がある感じ。Porcelain light surrounding an observable blue depth.'
colors:
  ink: '#183e4b'
  body: '#3f5e68'
  muted: '#59717a'
  paper: '#f7faf9'
  mist: '#eaf2f2'
  line: '#cbdcde'
  ocean: '#1b657b'
  deep: '#153e56'
  danger: '#9e3547'
  warning: '#805613'
  white: '#ffffff'
  chart-water: '#e6eff0'
  chart-grid: '#9fbfc8'
  journey: '#8c4d20'
typography:
  display:
    fontFamily: "'Zen Kaku', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif"
    fontSize: 'clamp(2rem, 3.5vw, 3.25rem)'
    fontWeight: 500
    lineHeight: 1.7
    letterSpacing: '-0.025em'
  headline:
    fontFamily: "'Zen Kaku', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif"
    fontSize: 'clamp(1.75rem, 3vw, 2.35rem)'
    fontWeight: 500
    lineHeight: 1.5
  section:
    fontFamily: "'Zen Kaku', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif"
    fontSize: 'clamp(1.65rem, 2.7vw, 2.2rem)'
    fontWeight: 500
    lineHeight: 1.5
  body:
    fontFamily: "'Zen Kaku', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif"
    fontSize: '15px'
    lineHeight: 1.8
  body-small:
    fontFamily: "'Zen Kaku', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif"
    fontSize: '14px'
    lineHeight: 2.1
  label:
    fontFamily: "'Zen Kaku', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif"
    fontSize: '13px'
  button:
    fontFamily: "'Zen Kaku', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', sans-serif"
    fontSize: '14px'
    fontWeight: 500
    lineHeight: '20px'
rounded:
  field: '8px'
  control: '12px'
  panel: '16px'
  pill: '9999px'
spacing:
  2: '8px'
  3: '12px'
  4: '16px'
  5: '20px'
  6: '24px'
  7: '28px'
  8: '32px'
  10: '40px'
components:
  button-primary:
    backgroundColor: '{colors.ocean}'
    textColor: '{colors.white}'
    typography: '{typography.button}'
    rounded: '{rounded.pill}'
    padding: '12px 28px'
  button-primary-hover:
    backgroundColor: '{colors.deep}'
  button-secondary:
    backgroundColor: 'transparent'
    textColor: '{colors.ink}'
    typography: '{typography.button}'
    rounded: '{rounded.pill}'
    padding: '12px 24px'
  button-secondary-hover:
    backgroundColor: '{colors.mist}'
  button-danger:
    backgroundColor: 'transparent'
    textColor: '{colors.danger}'
    typography: '{typography.button}'
    rounded: '{rounded.pill}'
    padding: '12px 24px'
  field:
    backgroundColor: '{colors.white}'
    textColor: '{colors.ink}'
    rounded: '{rounded.field}'
    padding: '12px 16px'
    width: '100%'
  action-panel:
    backgroundColor: '{colors.mist}'
    rounded: '{rounded.panel}'
    padding: '28px 32px'
  likert-option:
    backgroundColor: '{colors.white}'
    textColor: '{colors.ink}'
    rounded: '{rounded.control}'
    padding: '22px 14px'
    typography: '{typography.label}'
  chart-map:
    backgroundColor: '{colors.chart-water}'
    rounded: '{rounded.control}'
---

# Design System: 人格海図 ISOBATH

## Overview

**Creative North Star: "Porcelain Observation Basin / 明るいお風呂の中の深海"**

A bright, inviting porcelain surround opens onto a blue depth. Cool white, mist, soft Japanese lettering and generous horizontal space make observation feel approachable; concentrated blue gives the sea its depth. This is the implemented expression of the user’s “明るいお風呂の中に深海がある感じ” direction.

Operational pages use the same quiet materials with tighter reading and form widths. The illustrative basin and the observed chart remain visibly different: decoration explains the idea, while real data controls the chart, position and journey. No raster imagery is shipped; the signature contours and charts are code-authored SVG.

**Key Characteristics:**

- Light porcelain shell with mist surfaces and blue ink.
- Deep color concentrated in the basin and functional controls.
- Open record sections and thin rules, with occasional soft action panels.
- Visible keyboard focus, responsive controls and reduced motion.

Source: [direction contract](.impeccable/surfaces/src-routes-page-svelte.md), [PRODUCT.md](PRODUCT.md), and the built files referenced below. The frontmatter records implemented primitives; the sidecar carries motion, breakpoints, focus and component previews.

## Colors

The palette combines cool porcelain and muted blue ink with a concentrated ocean accent.

### Primary

- **Ocean:** primary actions, selected navigation, progress, field focus and chart density.
- **Deep:** the darker primary-button hover state.

### Secondary

- **Journey:** the warm brown used only for a participant’s position and trail on the chart. It separates personal history from aggregated density without ranking the terrain.

### Neutral

- **Paper:** shared page background.
- **Mist:** action panels, footer and gentle hover fills.
- **White:** field and option surfaces, primary-button text and map marker outlines.
- **Ink / Body / Muted:** headings and primary text / supporting prose / metadata.
- **Line:** quiet dividers, field borders and navigation separators.
- **Chart Water / Chart Grid:** the real map’s pale surface and restrained grid.

Danger and warning are semantic state colors, not decorative accents. Danger accompanies destructive actions and errors; warning accompanies uncertain or provisional results. Existing alert surfaces use Tailwind rose-50 and rose-200.

**The Porcelain Surround Rule.** Keep the shared shell light; reserve concentrated blue for controls, the basin and chart marks.

**The Observed Water Rule.** Encode chart density with one hue and opacity. Distinguish the illustrative basin from observed data; never invent a position or measurement to fill an empty surface.

Source: [shared palette](src/routes/layout.css:12), [real chart](src/lib/components/ChartMap.svelte:50). Basin-only HSL contours stay with their component, rather than becoming global interface accents.

## Typography

**Display and Body Font:** Zen Kaku, followed by Hiragino Kaku Gothic ProN, Yu Gothic and sans-serif. The font is self-hosted at `static/fonts/zen-kaku.ttf`; its license is [OFL.txt](static/fonts/OFL.txt). The face declaration supplies weight 500 with `font-display: swap`. Other requested utility weights use browser synthesis; there is no declared multiweight font family.

The soft Japanese grotesk supplies both character and clarity. Size, line spacing and blue emphasis provide hierarchy without a second display face.

### Hierarchy

- **Display:** fluid landing headline, medium weight with generous line spacing. At widths at or below 720px, its clamp becomes `clamp(2rem, 7.4vw, 3rem)` and line-height becomes 1.65.
- **Headline:** shared route and authentication titles.
- **Section:** landing narrative section headings; local context may use smaller fixed headings.
- **Body:** shared reading baseline. Supporting prose uses the smaller role with extra line spacing; the landing explanation is limited to 29em.
- **Label:** navigation and compact controls. Small metadata exists locally and is not a license to shrink essential instructions.
- **Button:** medium-weight control labels. Survey legends are 24px, increasing to 30px at the small breakpoint, with loose line-height.

Monospace appears only for numeric coordinates; it is not the display identity. Headings balance wrapping; paragraphs allow long content to wrap.

Source: [font and base styles](src/routes/layout.css:5), [landing type](src/routes/+page.svelte:104), [survey question](src/lib/components/LikertItem.svelte:16).

## Layout

The shared page container is centered, with a maximum width of 1040px and desktop padding of 60px 40px 40px. The public landing and navigation expand to 1328px; authentication narrows to 560px with 72px top padding. At widths at or below 640px, page padding is 32px 22px; authentication top padding becomes 40px. Navigation wraps and its links occupy a second, right-aligned row.

Spacing is mostly built on a four-pixel utility rhythm, with optical adjustments in the landing composition. The spacing primitives represent reused utility steps, not a ban on the observed custom gaps. Record sections use horizontal rules and 28px vertical padding. Action panels use the panel token and reduce to 24px padding on small screens.

The landing uses an asymmetric two-column introduction and broad narrative rows. At 1000px, gaps tighten and status content wraps. At 720px, introduction, story and principle sections become single columns. Profile records become single-column at 640px. Survey choices form five columns from the 640px utility breakpoint; below 640px they become full-width horizontal rows with a minimum height of 60px. The footer moves from one column to two at 640px and four at 1024px.

Source: [shared layout](src/routes/layout.css:110), [landing responsive layout](src/routes/+page.svelte:241), [Likert responsive layout](src/lib/components/LikertItem.svelte:57), [footer](src/lib/components/SiteFooter.svelte).

## Elevation & Depth

The system is flat in its interface surfaces. Tonal layers, one-pixel borders and an uninterrupted contour field produce depth without structural shadows. The basin uses 22 authored HSL contour levels; fine strokes and a faint grid reveal the surface. These mathematical contours are an illustration, not a statistical output.

**The Quiet Depth Rule.** Use contour layers, tonal surfaces and fine borders for depth; the shipped system has no structural box shadows.

The observation cursor eases over 650ms using `cubic-bezier(0.16, 1, 0.3, 1)`. Likert color changes use 180ms ease-out. Other utility transitions use the installed Tailwind defaults. Reduced motion sets animation and transition durations to 0.01ms and removes smooth scrolling. Focus rings are interaction cues, not elevation.

Source: [observation basin](src/lib/components/ObservationBasin.svelte:6), [cursor motion](src/lib/components/ObservationBasin.svelte:134), [reduced motion](src/routes/layout.css:258).

## Shapes

Ordinary fields use softly rounded corners; options and the chart use the control radius; action panels use the larger panel radius. Buttons are pills. Keep these ordinary shapes distinct from the basin’s arched top and gently rounded base: `48% 48% 18px 18px / 32% 32% 18px 18px`, reducing at 640px to `44% 44% 12px 12px / 28% 28% 12px 12px`. The basin maintains a 640:520 aspect ratio; the real chart is square.

Fine borders structure navigation, form controls and records. SVG line icons support labels; they do not become ornamental card illustrations.

Source: [shared utilities](src/routes/layout.css:92), [basin geometry](src/lib/components/ObservationBasin.svelte:102).

## Components

### Buttons

Calm, rounded controls with a minimum height of 48px. Primary buttons use ocean fill and white text, darkening on hover. Secondary buttons use transparent fill, line borders and ink text, changing to mist fill with an ocean border on hover. Destructive buttons use danger text and border, with rose-50 hover fill. Disabled shared buttons retain their geometry, use half opacity and a not-allowed cursor. Authentication actions expand to the form width.

All keyboard-focused controls inherit a 2px ocean outline with a 5px offset. There is no additional shared pressed-state treatment.

### Inputs / Fields

White, full-width fields use line borders, 48px minimum height and an 8px margin above. Focus changes the border and form-plugin ring to ocean while preserving the shared focus-visible outline. Errors are separate semantic alert paragraphs with danger text on a pale rose surface; do not infer an unimplemented field-level error variant.

### Navigation

The wordmark and service descriptor sit opposite compact textual links. Current and hovered top navigation links gain ocean color and underline. App tabs use muted text at rest, ocean text and a 2px bottom border for the current page. The skip link becomes visible on focus. Locale switching remains a labeled navigation link.

### Cards / Containers

Mist action panels group a decision and its supporting text. Observation records remain open on paper, separated by thin rules. Avoid treating every record as a card. The existing panel has no hover elevation or decorative icon header.

### Likert Options

Each answer is a native button in a disabled-capable fieldset. Desktop options are vertical, with a numbered mist circle, a 150px minimum height and a thin line border. Hover changes border to ocean and fill to mist. The small-screen variant is a compact horizontal row. Choosing an answer invokes the questionnaire action; there is no persistent selected-card style in this component.

### Observation Basin

A code-authored SVG contour study with an arched silhouette, white observation crosshair and a functional dark-blue label. Pointer movement, arrow keys, click and touch activation move the point; an accessible description explains the control. A visible caption identifies the image as illustrative. The sidecar shows a static component preview; the shipped Svelte component owns the interactive behavior.

### Chart Map

A square map with pale water, fine grid, ocean density cells and optional brown position or trail. Density alpha ranges from 0.15 to 0.85 according to observed counts. Position markers have white outlines. Missing chart data leaves the grid empty; real position and trail marks are conditional. The component carries an accessible image label.

Source: [utilities and focus](src/routes/layout.css), [auth form](<src/routes/(client)/auth/login/+page.svelte>), [app navigation](<src/routes/(client)/(app)/+layout.svelte>), [Likert options](src/lib/components/LikertItem.svelte), [basin](src/lib/components/ObservationBasin.svelte), [chart](src/lib/components/ChartMap.svelte).

## Do's and Don'ts

### Do:

- Do use the shared ocean, ink, paper, mist and line tokens for new screens.
- Do preserve readable Japanese line spacing and let translated labels wrap.
- Do use real chart data and retain explicit illustrative captions on authored contour studies.
- Do retain visible focus, semantic labels, native controls and reduced-motion behavior.
- Do keep task screens open, using separators for records and mist panels for grouped actions.

### Don't:

- Don’t turn the shared shell into a dark dashboard or neon sea.
- Don’t encode personality positions as a better-to-worse color scale.
- Don’t replace explanatory text or controls with ornamental icon cards.
- Don’t carry the basin silhouette onto ordinary fields, records or dialogs.
- Don’t introduce stock or generated raster artwork as though it were a measured chart.
