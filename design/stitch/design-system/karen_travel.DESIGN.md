---
name: Karen Travel
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
  on-surface-variant: '#59413c'
  inverse-surface: '#33302a'
  inverse-on-surface: '#f7f0e6'
  outline: '#8d706a'
  outline-variant: '#e1bfb8'
  surface-tint: '#b02e15'
  primary: '#ad2c12'
  on-primary: '#ffffff'
  primary-container: '#cf4429'
  on-primary-container: '#fffbff'
  inverse-primary: '#ffb4a4'
  secondary: '#6f5674'
  on-secondary: '#ffffff'
  secondary-container: '#f6d5fa'
  on-secondary-container: '#745a79'
  tertiary: '#7b5500'
  on-tertiary: '#ffffff'
  tertiary-container: '#9a6c00'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdad3'
  primary-fixed-dim: '#ffb4a4'
  on-primary-fixed: '#3e0500'
  on-primary-fixed-variant: '#8d1600'
  secondary-fixed: '#f9d8fd'
  secondary-fixed-dim: '#dcbce0'
  on-secondary-fixed: '#28132e'
  on-secondary-fixed-variant: '#563e5c'
  tertiary-fixed: '#ffdeab'
  tertiary-fixed-dim: '#f8bc4f'
  on-tertiary-fixed: '#271900'
  on-tertiary-fixed-variant: '#5f4100'
  background: '#fff8f0'
  on-background: '#1e1b15'
  surface-variant: '#e8e2d8'
typography:
  display:
    fontFamily: Vazirmatn
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 68px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Vazirmatn
    fontSize: 36px
    fontWeight: '800'
    lineHeight: 52px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Vazirmatn
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 42px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Vazirmatn
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 34px
    letterSpacing: 0em
  title-lg:
    fontFamily: Vazirmatn
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: 0em
  title-md:
    fontFamily: Vazirmatn
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: 0em
  body-lg:
    fontFamily: Vazirmatn
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: 0em
  body-md:
    fontFamily: Vazirmatn
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-sm:
    fontFamily: Vazirmatn
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  label-lg:
    fontFamily: Vazirmatn
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0em
  label-md:
    fontFamily: Vazirmatn
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0em
  label-sm:
    fontFamily: Vazirmatn
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-desktop: 1.5rem
  margin: 3.5rem
  margin-desktop: 3.5rem
  space-xs: 0.375rem
  space-sm: 0.75rem
  space-md: 1.25rem
  space-lg: 1.75rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes an inviting, culturally rooted, and premium travel booking experience for the Iranian tourism and flight market. Combining the seamless transactional utility of platforms like Alibaba.ir with the curated, inspirational visual storytelling of Lastsecond, the interface evokes the warmth of Persian hospitality alongside the dependable precision required for multi-modal travel bookings.

The visual direction merges **Warm Editorial Minimalism** with **Organic Tactility**:
- An earthy, sunlit canvas (Cream and Soft Paper) replaces clinical cold whites, creating an unhurried, resort-like aura.
- Deep Plum provides high-contrast editorial weight and authority without the sterility of pure black.
- Vibrant Coral and Warm Gold introduce energetic accents designed to guide booking decisions, signal promotions, and celebrate milestones.
- Generous, rounded surfaces (20px to 28px) and pill-shaped interactive anchors convey approachability, leisure, and tactile ease.
- Visual flow is strictly RTL (Right-to-Left), ensuring native physical reading ergonomics, flipped directional icons, and intuitive logical margins.

## Colors

The palette balances deep historic sophistication with high-conversion e-commerce clarity:

- **Primary Accent (`#EF5B3D` Coral)**: The decisive conversion engine. Used exclusively for primary calls-to-action (e.g., flight and hotel searches, checkout triggers), urgency indicators, flight departure paths, and promotional chips.
- **Secondary / Deep Brand (`#2A1530` Deep Plum)**: The foundational ink. Applied across hero headers, footers, primary headings, navbars, and high-emphasis body text. Replaces standard charcoal with a rich, plum undertone.
- **Tertiary Accent (`#EFB448` Warm Gold)**: Used for high-trust contextual signals: star ratings, VIP lounge markers, loyalty coin balances, and limited-time discounts.
- **Canvas (`#F5EEE4` Cream)**: The primary ambient background. Establishes a warm, matte baseline that reduces glare during extended travel comparisons.
- **Surface (`#FFFAF4` Soft Paper)**: The primary card and modal container background, sitting cleanly above the Cream canvas.
- **Muted Text (`#7F6D79`)**: Calibrated for secondary information, metadata, Persian calendar timestamps, airline baggage rules, and inactive states.
- **Structural Lines (`#E7DCD4`)**: Delicate, warm dividers and low-contrast borders preserving card contours against the cream canvas.

## Typography

Vazirmatn is deployed across all text layers to provide harmonious Persian typographic cadence. Because the Persian Nastaliq and Naskh scripts occupy wider vertical spans with extended ascenders and descenders, line-height ratios are expanded to a minimum of 1.5x–1.7x for body copy to prevent glyph collision and reading fatigue.

Typographic Rules:
- **Numerical Localization**: Render all pricing, flight hours, dates (Jalali calendar), and seat counts with native Persian numeral variants (`font-feature-settings: "ss01"` or localized Vazirmatn digits).
- **RTL Baseline**: Ensure `dir="rtl"` is hard-coded at the root level. Text alignment defaults to right (`text-align: right`), with prices and duration indicators right-aligned or balanced symmetrically inside flight itinerary tracks.
- **Weight Calibration**: Body text avoids light weights; `400` (Regular) is the base standard, stepping up to `600` (SemiBold) and `700`/`800` (Bold/ExtraBold) for headlines to ensure clarity in Arabic/Persian letterforms.

## Layout & Spacing

This design system targets an optimal desktop resolution of **1440px**:

- **Grid Architecture**: A 12-column fluid grid system bounded by a max-width container of `1320px`, flanked by `56px` (`3.5rem`) canvas margins and `24px` (`1.5rem`) gutters between columns.
- **Search Engine Island**: The focal hero search module spans all 12 columns, incorporating an inner grid of 4 to 5 input segments for origin, destination, departure/return dates, and passenger counts.
- **RTL Spatial Offsets**: Margins and padding follow physical logical properties: `margin-inline-start`, `padding-inline-end`. Icons inside text fields and buttons automatically anchor to the physical right (start), with text trailing toward the left.
- **Component Padding Scale**: Internal card paddings follow a generous structure: `24px` to `28px` on main hotel/flight cards to breathe naturally within their heavy border-radii.

## Elevation & Depth

Visual hierarchy uses warm, low-opacity plum ambient shadows paired with soft card surfaces to produce an effortless, sunlit layering effect:

- **Level 0 (Flat Canvas)**: Cream base (`#F5EEE4`) with zero shadow.
- **Level 1 (Card & Content Containers)**: Surface cards (`#FFFAF4`) framed by a fine border (`1px solid #E7DCD4`) and a subtle plum-tinted shadow: `0 4px 20px -2px rgba(42, 21, 48, 0.04)`.
- **Level 2 (Interactive Hover & Filter Drawers)**: Elevated flight tickets and hover states: `0 12px 32px -4px rgba(42, 21, 48, 0.08)`, border subtle shift toward `#D8C8BD`.
- **Level 3 (Search Hero & Popovers)**: Date picker calendars, passenger selectors, and sticky search bars: `0 20px 40px -6px rgba(42, 21, 48, 0.12)`.
- **Level 4 (Modal & Booking Checkout Confirmation)**: Deep overlays with a plum wash: `rgba(42, 21, 48, 0.4)` backdrop blur of `8px` and shadow `0 28px 56px -10px rgba(42, 21, 48, 0.22)`.

## Shapes

The shape vocabulary uses sweeping, soft geometry inspired by travel fluidity and Persian architectural curves:

- **Cards & Content Blocks**: Outer containers, flight ticket cards, hotel listings, and curated tour modules apply a distinct `24px` radius (`rounded-lg` / `rounded-xl` equivalent in this custom system), scaling up to `28px` for hero search consoles.
- **Buttons & Filter Chips**: Generous full-pill shapes (`border-radius: 9999px`) for search triggers, interactive category filters (Flights, Hotels, Villas, Trains), and promotional badges.
- **Form Inputs**: Deep rounded rectangles (`16px`) that nestle within the parent search island without creating visual friction.
- **Inner Imagery**: Travel photography, destination previews, and airline badges carry matching `16px` to `20px` corner treatments with zero sharp angles.

## Components

### Buttons
- **Primary Action (Coral)**: Background `#EF5B3D`, label Soft Paper `#FFFAF4`, font-weight `700`, full pill radius (`9999px`), padding `14px 32px`. Hover state applies slight brightness boost with `box-shadow: 0 8px 20px -2px rgba(239, 91, 61, 0.35)`.
- **Secondary Action (Deep Plum Ghost/Outline)**: Border `1.5px solid #2A1530`, text `#2A1530`, background transparent. Hover transitions to `#2A1530` with `#FFFAF4` text.
- **Tertiary Accent Button (Warm Gold)**: Used for VIP reservations and instant discounts: background `#EFB448`, text `#2A1530`, pill-shaped.

### Flight & Hotel Search Bar
- Unified floating island container with `#FFFAF4` background, `28px` radius, and Level 3 ambient shadow.
- Separated internally by subtle vertical dividers (`1px solid #E7DCD4`).
- Interactive segments (Origin/Destination, Dates, Travelers) highlight with a warm cream `#F5EEE4` background on focus, maintaining seamless RTL tab order.

### Travel Cards (Hotels, Tours & Flights)
- Background `#FFFAF4`, radius `24px`, border `1px solid #E7DCD4`.
- **Flight Cards**: Structured horizontal flow from right to left: Origin time and airport on the right, airline badge and route progress bar in the center, and pricing with Coral CTA pill on the left.
- **Hotel Cards**: High-aspect imagery on the right (or top in grid view) with embedded Warm Gold rating pill (`#EFB448` with `#2A1530` text, displaying Persian numerals: e.g., `۴.۸ ★`).

### Input Fields & Pickers
- Background `#FFFFFF` inside panels, border `1px solid #E7DCD4`, radius `14px`, text color `#2A1530`, placeholder text `#7F6D79`.
- Active focus state features a crisp `2px` Coral border ring (`#EF5B3D`) with no harsh browser outline.
- Jalali calendar popover opens with right-anchored alignment, soft cream day-hover states, and coral range-selection highlights.

### Chips & Filter Tags
- Pill-shaped (`9999px`), padding `8px 20px`.
- Unselected: Soft Paper background `#FFFAF4`, border `1px solid #E7DCD4`, text `#7F6D79`.
- Selected: Deep Plum `#2A1530` background, text `#FFFAF4`, border `1px solid #2A1530`.