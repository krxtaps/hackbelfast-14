# Belfast Safety UI (Baseline)

React baseline UI for a Belfast-only safety app map.

## Why this map stack

- **OpenStreetMap + Leaflet (via react-leaflet)** is simple, free, open-source, and quick for hackathon prototypes.
- Google Maps is great but requires API keys and can add billing/usage overhead.

## Included baseline functionality

- Belfast-centered map in the **top 50%** of the app
- Control panel in the **bottom 50%** with 3 primary actions:
  - Minor Injuries
  - Sanctuary
  - Journey Planner (safer route demo)
- Placeholder points for:
  - Pharmacies
  - Clinics (minor injuries)
  - Sanctuaries
- Buttons route from demo user start point to selected destination
- Browser geolocation request to use the user’s real current location for routes
- Journey planner currently draws a safer placeholder path via low-risk street segment
- Color-coded **street safety grading** for Belfast roads (low/medium/high)
- Risk-level guidance card with practical safety tips
- Robust UX states:
  - Offline state
  - Location denied/error fallback state
  - Belfast context hook error state
  - Route unavailable messaging
- Accessibility polish:
  - Skip-to-controls link for keyboard users
  - Live region announcements for location and state updates
  - Alert/status semantics for warning and error banners
  - Strong focus-visible outlines
  - Reduced motion support
- Belfast-specific data hook (`src/hooks/useBelfastContext.js`) for area profiles and context advisory
- Route scoring card with weighted factors (lighting, footfall, CCTV, emergency access, street risk, route complexity)
- Syncfusion components already used for:
  - Action buttons
  - Location detail dialog

## Run locally

```bash
npm install
npm run dev
```

## Syncfusion integration notes (React)

This project already includes Syncfusion packages and imports:

- `@syncfusion/ej2-react-buttons`
- `@syncfusion/ej2-react-popups`

If you want more Syncfusion UI elements next:

1. Install extra package(s), for example:
   ```bash
   npm i @syncfusion/ej2-react-inputs @syncfusion/ej2-react-navigations
   ```
2. Import required theme CSS in `src/main.jsx`.
3. Use components in `src/App.jsx`, e.g. `TextBoxComponent`, `TabComponent`, or `SidebarComponent`.
4. Keep map-specific logic in plain React + Leaflet while using Syncfusion for shell/layout/forms.

For production licensing, review Syncfusion licensing terms for your team/account.

Optional license registration snippet (add in `src/main.jsx` before rendering):

```jsx
import { registerLicense } from "@syncfusion/ej2-base";
registerLicense("YOUR_LICENSE_KEY");
```
