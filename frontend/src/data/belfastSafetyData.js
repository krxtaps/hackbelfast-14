export const userStartPosition = [54.5973, -5.9301];

export const belfastAreaProfiles = [
  {
    id: "city-core",
    name: "City Centre",
    center: [54.5972, -5.9304],
    lighting: 0.86,
    footfall: 0.82,
    cctvCoverage: 0.9,
    emergencyAccess: 0.9
  },
  {
    id: "south-belfast",
    name: "South Belfast",
    center: [54.5835, -5.9321],
    lighting: 0.72,
    footfall: 0.64,
    cctvCoverage: 0.68,
    emergencyAccess: 0.76
  },
  {
    id: "east-belfast",
    name: "East Belfast",
    center: [54.5968, -5.8909],
    lighting: 0.7,
    footfall: 0.61,
    cctvCoverage: 0.66,
    emergencyAccess: 0.74
  },
  {
    id: "north-belfast",
    name: "North Belfast",
    center: [54.6218, -5.9442],
    lighting: 0.66,
    footfall: 0.58,
    cctvCoverage: 0.62,
    emergencyAccess: 0.69
  },
  {
    id: "west-belfast",
    name: "West Belfast",
    center: [54.5889, -5.9818],
    lighting: 0.6,
    footfall: 0.53,
    cctvCoverage: 0.56,
    emergencyAccess: 0.64
  }
];

export const supportLocations = [
  // ── Pharmacies ──────────────────────────────────────────────────────────
  {
    id: "ph-1",
    type: "pharmacy",
    name: "Boots Belfast City Centre",
    address: "35–47 Donegall Place, Belfast BT1 5AB",
    coords: [54.5982, -5.9296],
    phone: "028 9024 2332",
    hours: "Mon–Sat 8:30am–6pm · Sun 12pm–5pm",
    details: "Large pharmacy with private consultation room.",
    services: [
      "Minor Ailments Service (no GP referral needed)",
      "Wound care & first aid supplies",
      "Blood pressure monitoring",
      "Emergency contraception",
      "Prescription collection & delivery",
      "Travel health & vaccinations"
    ],
    whatToExpect:
      "Walk in and speak to a pharmacist directly. Private consultation booths available. No appointment needed for minor ailments."
  },
  {
    id: "ph-2",
    type: "pharmacy",
    name: "Well Pharmacy Ormeau",
    address: "118 Ormeau Road, Belfast BT7 2ED",
    coords: [54.5874, -5.9232],
    phone: "028 9064 8901",
    hours: "Mon–Fri 9am–6pm · Sat 9am–5pm",
    details: "Community pharmacy with minor ailment service.",
    services: [
      "Minor ailment advice & medication",
      "Inhaler technique review",
      "Smoking cessation support",
      "Medication usage reviews",
      "Emergency supply service"
    ],
    whatToExpect:
      "Friendly community pharmacy. Pharmacist available without appointment for most queries."
  },
  {
    id: "ph-3",
    type: "pharmacy",
    name: "McCaig's Pharmacy North",
    address: "450 Antrim Road, Belfast BT15 5GH",
    coords: [54.6201, -5.9363],
    phone: "028 9077 1234",
    hours: "Mon–Sat 9am–9pm · Sun 11am–5pm",
    details: "Extended-hours pharmacy serving North Belfast.",
    services: [
      "Late-night minor ailment service",
      "Pain relief & wound care",
      "Needle exchange programme",
      "Diabetes care supplies",
      "Free blood pressure checks"
    ],
    whatToExpect:
      "Extended hours for after-hours needs. Walk in directly — no appointment required."
  },

  // ── Urgent Care Clinics ──────────────────────────────────────────────────
  {
    id: "cl-1",
    type: "clinic",
    name: "Belfast Walk-In Care Centre",
    address: "2 Knockbracken Healthcare Park, Saintfield Road, Belfast BT8 8BH",
    coords: [54.5594, -5.9169],
    phone: "028 9504 2000",
    hours: "Mon–Sun 8am–10pm",
    details: "Walk-in urgent care for non-emergency conditions.",
    services: [
      "Minor injury assessment & treatment",
      "X-ray facilities on-site",
      "Wound suturing & dressings",
      "Fracture management",
      "Specialist referrals",
      "Infection diagnosis & treatment"
    ],
    whatToExpect:
      "Walk in without an appointment. A triage nurse will assess you. Bring any medications you take. Average wait 30–90 minutes."
  },
  {
    id: "cl-2",
    type: "clinic",
    name: "East Belfast Urgent Care",
    address: "Upper Newtownards Road, Belfast BT4 3LP",
    coords: [54.6011, -5.8843],
    phone: "028 9504 8000",
    hours: "Mon–Sun 9am–9pm",
    details: "Treats non-life-threatening injuries and infections.",
    services: [
      "Injury assessment & treatment",
      "Skin infection treatment",
      "Minor burns care",
      "Mental health first contact",
      "Social prescribing link worker"
    ],
    whatToExpect:
      "Walk in for urgent care. Not an A&E — for emergencies call 999. Average wait under 45 minutes."
  },
  {
    id: "cl-3",
    type: "clinic",
    name: "West Belfast Health Centre",
    address: "51 Glen Road, Belfast BT11 8BB",
    coords: [54.5875, -5.9801],
    phone: "028 9063 3500",
    hours: "Mon–Fri 8am–6pm",
    details: "GP-led urgent care with community nursing.",
    services: [
      "Same-day urgent appointments",
      "Community nursing support",
      "Mental health assessment",
      "Children's health services",
      "Chronic condition management"
    ],
    whatToExpect:
      "Call ahead if possible but walk-ins accepted for urgent cases. Interpreter services available on request."
  },

  // ── Sanctuaries ─────────────────────────────────────────────────────────
  {
    id: "sa-1",
    type: "sanctuary",
    name: "Community Sanctuary Hub North",
    address: "12 North Queen Street, Belfast BT15 1HB",
    coords: [54.6175, -5.9431],
    phone: "028 9089 0100",
    hours: "Open 24 / 7",
    details: "Safe space with trained volunteers and crisis escalation.",
    services: [
      "Immediate safe haven — no questions asked",
      "Trained crisis support volunteers",
      "Police & emergency services liaison",
      "Anonymous reporting option",
      "Multilingual support staff",
      "Transport to safer location",
      "Secure phone & device charging"
    ],
    whatToExpect:
      "Just walk in. Staff will not pressure you. You can stay as long as you need. Completely confidential."
  },
  {
    id: "sa-2",
    type: "sanctuary",
    name: "Harbour Sanctuary Point",
    address: "Donegall Quay, Belfast BT1 3NF",
    coords: [54.6078, -5.9058],
    phone: "028 9033 4400",
    hours: "Open 24 / 7",
    details: "Immediate refuge with council welfare and housing links.",
    services: [
      "Short-term refuge space",
      "Belfast City Council welfare link",
      "Housing support referral",
      "Domestic abuse safe pathway",
      "Legal aid signposting",
      "Hot food & warm space"
    ],
    whatToExpect:
      "Named as an official Safe Space venue. Walk in and show our app. No referral letter needed."
  },
  {
    id: "sa-3",
    type: "sanctuary",
    name: "The Well – South Belfast",
    address: "Botanic Avenue, Belfast BT7 1JL",
    coords: [54.5855, -5.9335],
    phone: "028 9023 7777",
    hours: "Mon–Sun 7am–11pm",
    details: "Community wellbeing drop-in with mental health support.",
    services: [
      "Mental health first aid",
      "Drop-in counselling sessions",
      "Youth sanctuary space (under 25)",
      "LGBTQ+ affirming staff",
      "Food pantry access",
      "Emergency housing signposting"
    ],
    whatToExpect:
      "Welcoming community space. No appointment needed. Peer support workers available at all times."
  },
  {
    id: "sa-4",
    type: "sanctuary",
    name: "Cultúrlann – West Belfast",
    address: "216 Falls Road, Belfast BT12 6AH",
    coords: [54.5917, -5.9699],
    phone: "028 9096 4180",
    hours: "Mon–Sat 9am–9pm",
    details: "Cultural safe space with community crisis support.",
    services: [
      "Safe space for those in distress",
      "Irish-language support workers",
      "Community mediator on call",
      "Young person support (under 18)",
      "Restorative justice referrals"
    ],
    whatToExpect:
      "Culturally sensitive safe space. Bilingual Irish/English support. Community-led and widely trusted."
  }
];

export const dangerZones = [
  {
    id: "dz-north",
    name: "North Belfast Interface",
    level: "high",
    polygon: [
      [54.630, -5.961],
      [54.630, -5.926],
      [54.610, -5.926],
      [54.610, -5.961]
    ]
  },
  {
    id: "dz-west",
    name: "West Belfast Corridor",
    level: "high",
    polygon: [
      [54.602, -6.010],
      [54.602, -5.975],
      [54.576, -5.975],
      [54.576, -6.010]
    ]
  },
  {
    id: "dz-east",
    name: "East Belfast",
    level: "medium",
    polygon: [
      [54.614, -5.905],
      [54.614, -5.870],
      [54.591, -5.870],
      [54.591, -5.905]
    ]
  },
  {
    id: "dz-south",
    name: "South Belfast",
    level: "low",
    polygon: [
      [54.590, -5.952],
      [54.590, -5.915],
      [54.566, -5.915],
      [54.566, -5.952]
    ]
  },
  {
    id: "dz-centre",
    name: "City Centre",
    level: "low",
    polygon: [
      [54.608, -5.945],
      [54.608, -5.920],
      [54.590, -5.920],
      [54.590, -5.945]
    ]
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
  },
  {
    id: "st-6",
    name: "Falls Road",
    level: "medium",
    path: [
      [54.5933, -5.9601],
      [54.5918, -5.9651],
      [54.5901, -5.9701]
    ],
    notes: "Busy arterial road with variable evening footfall."
  },
  {
    id: "st-7",
    name: "Shankill Road",
    level: "medium",
    path: [
      [54.6002, -5.9610],
      [54.5989, -5.9660],
      [54.5975, -5.9710]
    ],
    notes: "Community thoroughfare — moderate risk at night."
  }
];

export const safetyTips = {
  low: [
    "Stay in well-lit routes where possible.",
    "Share your live location with a trusted contact.",
    "Keep emergency contacts saved and easy to reach."
  ],
  medium: [
    "Avoid isolated shortcuts, especially at night.",
    "Keep emergency contacts and transport options ready.",
    "Use the Journey Planner to find safer routes."
  ],
  high: [
    "Move to a busy public area immediately.",
    "Head to the nearest sanctuary and contact emergency services if needed.",
    "Call 999 if you feel in immediate danger — do not wait."
  ]
};
