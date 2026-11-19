---
name: Warm Persian Horizon
colors:
  surface: '#fff8f0'
  surface-dim: '#e0d9cf'
  surface-bright: '#fff8f0'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#faf3e9'
  surface-container: '#f4ede3'
  surface-container-high: '#eee7dd'
  surface-container-highest: '#e8e2d8'
  on-surface: '#1e1b15'
  on-surface-variant: '#4c454c'
  inverse-surface: '#33302a'
  inverse-on-surface: '#f7f0e6'
  outline: '#7d747c'
  outline-variant: '#cec3cc'
  surface-tint: '#6f5674'
  primary: '#09000f'
  on-primary: '#ffffff'
  primary-container: '#2a1530'
  on-primary-container: '#987c9d'
  inverse-primary: '#dcbce0'
  secondary: '#b02e15'
  on-secondary: '#ffffff'
  secondary-container: '#f96243'
  on-secondary-container: '#5c0b00'
  tertiary: '#050200'
  on-tertiary: '#ffffff'
  tertiary-container: '#2a1a00'
  on-tertiary-container: '#af7c0c'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#f9d8fd'
  primary-fixed-dim: '#dcbce0'
  on-primary-fixed: '#28132e'
  on-primary-fixed-variant: '#563e5c'
  secondary-fixed: '#ffdad3'
  secondary-fixed-dim: '#ffb4a4'
  on-secondary-fixed: '#3e0500'
  on-secondary-fixed-variant: '#8d1600'
  tertiary-fixed: '#ffdeab'
  tertiary-fixed-dim: '#f8bc4f'
  on-tertiary-fixed: '#271900'
  on-tertiary-fixed-variant: '#5f4100'
  background: '#fff8f0'
  on-background: '#1e1b15'
  surface-variant: '#e8e2d8'
typography:
  display-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 64px
  display-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '800'
    lineHeight: 44px
  headline-xl:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 50px
  headline-xl-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 38px
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 40px
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-sm: 1rem
  margin: 3rem
  margin-mobile: 1rem
  space-xs: 0.375rem
  space-sm: 0.75rem
  space-md: 1.25rem
  space-lg: 2rem
  space-xl: 3rem
---

## Brand & Style

This design system expresses a warm, hospitable, and premium travel agency identity tailored specifically for Iranian and Persian-speaking travelers. Rooted in traditional Persian warmth and elevated through contemporary digital minimalism, the aesthetic balances the reliability of institutional travel platforms with the bespoke allure of curated journeys.

### Core Character & Mood
- **Persian Hospitality & Modernity:** Anchored by warm cream foundations, rich plum structures, and energetic coral accents, the interface feels welcoming, luxurious, and culturally authentic without resorting to historicist clichés.
- **Tone:** Authoritative, comforting, inspiring, and frictionless.
- **Design Philosophy:** Organic structure with soft, tactile architecture. Generous surface radii, airy typographic hierarchies, and low-contrast warm boundaries make long search sessions relaxed and reassuring.
- **Directionality:** Strict right-to-left (RTL) reading geometry across all layouts, icon flips, reading rhythms, and micro-interactions.

## Colors

The palette leverages high-contrast deep plum paired against creamy, soft-paper tones to eliminate harsh digital whites, complemented by Persian coral and saffron-tinted gold.

### Palette Architecture
- **Primary (`#2A1530` - Deep Plum):** The structural backbone. Used for high-emphasis headlines, navigation bars, primary text, dark-mode-leaning headers/footers, and authoritative structural borders.
- **Secondary / Primary CTA (`#EF5B3D` - Persian Coral):** The vibrant catalyst. Applied strictly to primary conversion points (booking triggers, flight search confirmation buttons, urgency badges, active states).
- **Tertiary (`#EFB448` - Warm Gold):** The prestige accent. Reserved for star ratings, loyalty perks, exclusive discounts, VIP cabin tags, and flight stopover highlights.
- **Canvas Neutral (`#F5EEE4` - Background Cream):** The main application viewport backdrop. Creates a warm, tactile reading canvas that minimizes eye fatigue.
- **Card Surface (`#FFFAF4` - Soft Paper):** Slightly elevated container surface providing a gentle, crisp contrast above the canvas cream.
- **Muted Slate Plum (`#7F6D79`):** Subtitle text, placeholder states, inactive icons, and metadata (baggage allowance, flight duration).
- **Structural Border (`#E7DCD4`):** Whisper-thin boundaries for search field segmentation, card rims, and table separators.

## Typography

Typographic scale and balance are calibrated for the Vazirmatn font stack (backed by Plus Jakarta Sans for Latin fallback and numeric parity). Persian script requires slightly larger line heights (between 1.5x and 1.75x) to maintain clarity for diacritics, descenders, and ligatures.

### RTL Typographic Rules
- **Font Stack:** Primary font is `Vazirmatn`, followed by `Plus Jakarta Sans`, and generic `system-ui, sans-serif`.
- **Numerals:** Currency (تومان / ریال), dates (Jalali calendar), and flight times default to Persian digits (`font-feature-settings: "numr" 1, "ss01" 1`) for native contexts, while airport IATA codes (THR, DXB, IST) enforce Western alphanumeric characters.
- **Tracking & Spacing:** Avoid positive letter-spacing on connected Persian glyphs as it fragments cursive word shapes. Latin labels may retain neutral tracking.
- **Headings:** Headlines employ Bold (700) and ExtraBold (800) weights to anchor eye movement rightward.

## Layout & Spacing

The layout is built upon a 12-column fluid grid system optimized for a primary desktop target of 1440px with a maximum inner container of 1320px.

### Grid & Structure
- **Desktop (1440px):** 12 columns, 24px (`1.5rem`) gutters, and 48px (`3rem`) page margins.
- **Tablet (768px - 1024px):** 8 columns, 16px (`1rem`) gutters, and 24px (`1.5rem`) margins.
- **Mobile (< 768px):** 4 columns, 12px gutters, and 16px (`1rem`) lateral margins.

### RTL Flow & Spacing Cadence
- **Horizontal Flow:** Hierarchy reads naturally right-to-left. Primary visual anchors (airline logos, origin cities, departure dates) anchor on the right; flight progression lines draw from right to left, terminating at destinations on the left.
- **Search Engine Modular Stack:** The primary search hero overlaps the hero visual with 28px outer card radii and an inner 16px to 20px padding rhythm.

## Elevation & Depth

Visual hierarchy uses warm, diffuse ambient layering instead of cold grayscale drop shadows. Every drop shadow is tinted with the core deep plum (`#2A1530`), blending seamlessly into the `#F5EEE4` cream background.

### Elevation Levels
- **Level 0 (Flat / Canvas):** Applied directly to `#F5EEE4` background panels.
- **Level 1 (Card Surface):** Used for flight listing cards, package items, and profile modules.
  - Border: `1px solid #E7DCD4`
  - Shadow: `0px 6px 20px -2px rgba(42, 21, 48, 0.04), 0px 2px 6px -1px rgba(42, 21, 48, 0.02)`
- **Level 2 (Active Search Engine & Filter Trays):**
  - Border: `1px solid rgba(231, 220, 212, 0.8)`
  - Shadow: `0px 14px 34px -4px rgba(42, 21, 48, 0.07), 0px 4px 12px -2px rgba(42, 21, 48, 0.03)`
- **Level 3 (Modals, Flight Details Drawer, Jalali Calendar Picker):**
  - Border: `1px solid #E7DCD4`
  - Shadow: `0px 24px 48px -6px rgba(42, 21, 48, 0.12), 0px 8px 16px -4px rgba(42, 21, 48, 0.04)`

## Shapes

The interface embraces generous, welcoming curved geometry that radiates approachability and modern comfort.

### Radius Scale
- **Macro Containers (Cards, Search Hero, Modal Windows):** 20px to 28px (`rounded-xl` and `rounded-2xl`). This softens large interface structures across the desktop viewport.
- **Interactive Controls (Buttons, Inputs, Selectors):** 12px to 16px (`rounded-md` to `rounded-lg`). Ensures actionable areas feel finger-friendly and distinct from page surfaces.
- **Pills & Micro-indicators (Badges, Flight Stop Counters, Status Chips):** 9999px (full pill).

## Components

### Buttons
- **Primary CTA (Book Now, Search Flights):** Surface `#EF5B3D` (Persian Coral), label `#FFFFFF`, border-radius 14px. Interactive hover transitions to `#D94C30` with subtle elevation lift.
- **Secondary Action (Filter, Modify Search):** Surface `#FFFAF4`, text `#2A1530`, border `1.5px solid #E7DCD4`, hover background `#F5EEE4`.
- **Tertiary / Ghost:** Transparent surface, text `#2A1530`, hover background `rgba(42, 21, 48, 0.05)`.
- **Padding:** Vertical `12px` to `14px`, horizontal `24px` to `28px`.

### Search Box & Input Fields
- **Container Structure:** Nested inside a Level 2 paper card (`#FFFAF4`) with 24px radius.
- **Input Cells:** Surface `#FFFFFF`, border `1.5px solid #E7DCD4`, border-radius 12px, font-size 15px.
- **RTL Arrangement:** Label on the upper right, input content flows right to left. Leading icon rests on the right edge, calendar/dropdown arrows stay on the left.
- **Focus State:** Border changes to `#2A1530`, outline ring `3px solid rgba(42, 21, 48, 0.12)`.

### Flight & Tour Cards
- **Architecture:** Horizontal desktop layout on `#FFFAF4` with a 20px border radius and 1px `#E7DCD4` outline.
- **Right Segment:** Airline brand, flight number, cabin class.
- **Center Segment:** Origin time & airport (right), flight trajectory timeline (flowing right-to-left with duration and stopover tags above), destination time & airport (left).
- **Left Segment:** Price block in `#2A1530` with Persian Tomans, currency sub-labels in `#7F6D79`, and primary coral CTA button (`#EF5B3D`).

### Chips & Filter Badges
- **Flight Attributes (Non-stop, Baggage included, Refundable):** Pill radius (9999px), background `#F5EEE4`, text `#2A1530`, font-size 12px.
- **Special Discounts & Loyalty Badges:** Surface `rgba(239, 180, 72, 0.15)`, text `#8A5C00`, accent icon `#EFB448`.

### Jalali Date Picker
- **Format:** Dual calendar popover rendered in Persian right-to-left layout.
- **Selection State:** Start and end ranges filled with soft coral tint (`rgba(239, 91, 61, 0.12)`), active endpoints in solid `#EF5B3D` with white text.
- **Numerals:** Native Persian figures (۱، ۲، ۳...).

### Checkboxes & Radios
- **Radius:** Checkboxes 6px, Radio buttons circle.
- **Active State:** Background `#2A1530` with a clean white tick or inner dot.
- **Label Alignment:** Label text positioned to the left of the control box, maintaining RTL ergonomics.