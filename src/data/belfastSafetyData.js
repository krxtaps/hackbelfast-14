export const userStartPosition = [54.5973, -5.9301];

export const supportLocations = [
  {
    id: "ph-1",
    type: "pharmacy",
    name: "Boots Belfast City Centre",
    coords: [54.5982, -5.9296],
    details: "Open late. First aid supplies, pain relief, wound care guidance."
  },
  {
    id: "ph-2",
    type: "pharmacy",
    name: "Well Pharmacy Ormeau",
    coords: [54.5874, -5.9232],
    details: "Minor ailment advice and non-emergency medication support."
  },
  {
    id: "cl-1",
    type: "clinic",
    name: "Belfast Walk-In Care (Demo)",
    coords: [54.5934, -5.9369],
    details: "Minor injury assessment and referrals."
  },
  {
    id: "cl-2",
    type: "clinic",
    name: "East Belfast Urgent Care (Demo)",
    coords: [54.6011, -5.8843],
    details: "Treats non-life-threatening injuries and infections."
  },
  {
    id: "sa-1",
    type: "sanctuary",
    name: "Community Sanctuary Hub North",
    coords: [54.6175, -5.9431],
    details: "Safe space with trained volunteers and escalation support."
  },
  {
    id: "sa-2",
    type: "sanctuary",
    name: "Harbour Sanctuary Point",
    coords: [54.6078, -5.9058],
    details: "Immediate short-term refuge and local authority contact support."
  }
];

export const streetSafetySegments = [
  {
    id: "st-1",
    name: "Donegall Place",
    level: "low",
    path: [
      [54.5993, -5.9304],
      [54.5982, -5.9305],
      [54.5973, -5.9307]
    ],
    notes: "Busy, central, generally well-lit."
  },
  {
    id: "st-2",
    name: "Ormeau Road (Central)",
    level: "medium",
    path: [
      [54.5904, -5.9235],
      [54.5882, -5.9228],
      [54.5861, -5.9223]
    ],
    notes: "Mixed footfall and lighting by time of day."
  },
  {
    id: "st-3",
    name: "Springfield Road (West)",
    level: "high",
    path: [
      [54.5869, -5.9731],
      [54.5856, -5.9695],
      [54.5841, -5.966]
    ],
    notes: "Lower late-night activity in this demo model."
  },
  {
    id: "st-4",
    name: "Antrim Road (North)",
    level: "medium",
    path: [
      [54.6208, -5.9358],
      [54.6179, -5.9356],
      [54.6148, -5.9347]
    ],
    notes: "Moderate risk corridor in placeholder data."
  },
  {
    id: "st-5",
    name: "Oxford Street",
    level: "low",
    path: [
      [54.5967, -5.9244],
      [54.5977, -5.9256],
      [54.5987, -5.9269]
    ],
    notes: "Transit-heavy area with higher passive surveillance."
  }
];

export const safetyTips = {
  low: [
    "Stay in well-lit routes where possible.",
    "Share your live location with a trusted contact."
  ],
  medium: [
    "Avoid isolated shortcuts at night.",
    "Keep emergency contacts and transport options ready."
  ],
  high: [
    "Move to a busy public area immediately.",
    "Head to the nearest sanctuary point and contact emergency services if needed."
  ]
};
