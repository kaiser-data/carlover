# Carlover ADAC Integration — Loveable Developer Guide

This guide explains how to integrate the Carlover `/vehicle/lookup` endpoint into a Loveable app. The endpoint fetches **real, measured breakdown data** from ADAC (the German Automobile Club) — not LLM-generated statistics. The data is structured but partially in German; this guide covers translation, smart synthesis, image display, and correct attribution.

---

## Quick Start

```bash
POST https://<your-daytona-url>/vehicle/lookup
Content-Type: application/json

{
  "make": "BMW",      # optional — can be inferred from model
  "model": "X3",      # required — typo-tolerant ("X 3", "x3", "BMW X3" all work)
  "year": 2021        # optional — used for generation matching
}
```

**Rules:**
- `make` is optional. "Golf", "Polo", "Octavia" → brand inferred automatically.
- Typos are corrected: "Gollf" → Golf, "Vollkswagen" → VW, "Mersedes" → Mercedes-Benz.
- English model names work: "3 Series" → 3er, "C Class" → C-Klasse.
- If `found: false`, no ADAC data exists for that vehicle.

---

## Annotated Response

```jsonc
{
  // ── Normalised lookup ──────────────────────────────────────────────
  "normalized_make": "BMW",           // brand after typo correction
  "normalized_model": "X3",          // model after typo correction
  "year": 2021,                       // echoed back
  "corrections": [                    // list of corrections applied (empty if input was clean)
    "make: BMW X3 → BMW / X3"
  ],
  "found": true,                      // false = no ADAC page exists
  "elapsed_ms": 2841.2,               // response time in ms

  // ── Vehicle image ──────────────────────────────────────────────────
  // image_url: official ADAC vehicle photo, 1500 px wide, always JPEG
  // Use directly as <img src>. May be null for very rare models.
  "vehicle_info": {
    "make": "BMW",
    "model": "X3",
    "year_from": 2003,                // first model year on ADAC records
    "year_to": null,                  // null = still in production
    "description": "The BMW X3 is a …",  // English description from ADAC
    "image_url": "https://assets.adac.de/image/upload/…/bmw-x3.jpg",
    "adac_page_url": "https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/bmw/x3/",

    // ── Generations ────────────────────────────────────────────────
    "generations": [
      { "name": "F25",     "year_from": 2010, "year_to": 2017 },
      { "name": "G01/F97", "year_from": 2017, "year_to": null }
    ],

    // ── Pannenstatistik — year-by-year breakdown data ───────────────
    // This is ADAC's annual measured breakdown survey covering all registered
    // vehicles of that model year in Germany. Source data, not estimates.
    "reliability_by_year": [
      {
        "year": 2021,
        "breakdowns_per_1000": 1.4,   // measured breakdowns per 1,000 vehicles/year
        "rating": "sehr gut",          // ⚠️  GERMAN — see translation table below
        "rating_score": 0.95,          // numeric: 0.95=very good … 0.15=poor (use for logic)
        "generation_name": "G01/F97",  // which generation was sold that year
        "annual_mileage_km": 14000,    // km/year assumption used for calculation
        "class_thresholds": {          // ⚠️  GERMAN FIELD NAMES — thresholds for this vehicle's segment
          "sehr_gut":     2.0,         // ≤ 2.0  → rated "sehr gut"  (Very Good)
          "gut":          9.4,         // ≤ 9.4  → rated "gut"       (Good)
          "befriedigend": 16.9,        // ≤ 16.9 → rated "befriedigend" (Satisfactory)
          "ausreichend":  24.3         // ≤ 24.3 → rated "ausreichend"  (Adequate)
                                       // > 24.3 → rated "mangelhaft"    (Poor)
        }
      }
      // … more years
    ]
  },

  // ── Known issues from ADAC defects database ────────────────────────
  // ⚠️  All text fields are in German — translate with an LLM (see section below)
  "issue_patterns": [
    {
      "pattern_name": "Motorölverlust",                   // German issue name
      "symptoms":     ["Ölflecken unter dem Fahrzeug"],   // German description
      "root_cause":   "Undichte Ölwannendichtung",        // German cause
      "solution":     "Dichtung ersetzen lassen",         // German solution
      "severity":     "medium",                           // English: low/medium/high/critical
      "affected_years": null
    }
  ]
}
```

---

## German Translation Reference

### Rating values (`rating` field)

| German (`rating`) | English | `rating_score` | Color suggestion |
|---|---|---|---|
| `sehr gut`      | Very Good    | 0.95 | `#22c55e` green  |
| `gut`           | Good         | 0.80 | `#84cc16` lime   |
| `befriedigend`  | Satisfactory | 0.60 | `#f59e0b` amber  |
| `ausreichend`   | Adequate     | 0.35 | `#f97316` orange |
| `mangelhaft`    | Poor         | 0.15 | `#ef4444` red    |

```typescript
const RATING_EN: Record<string, string> = {
  "sehr gut":     "Very Good",
  "gut":          "Good",
  "befriedigend": "Satisfactory",
  "ausreichend":  "Adequate",
  "mangelhaft":   "Poor",
};

// Emoji shorthand for compact display
const RATING_EMOJI: Record<string, string> = {
  "sehr gut": "🟢", "gut": "🟡", "befriedigend": "🟠",
  "ausreichend": "🔴", "mangelhaft": "⛔",
};
```

### Class threshold field names

```typescript
// The class_thresholds object uses German field names.
// Map them to English for display:
const THRESHOLD_EN: Record<string, string> = {
  sehr_gut:     "Very Good",
  gut:          "Good",
  befriedigend: "Satisfactory",
  ausreichend:  "Adequate",
};
```

### Common German issue terms (quick reference)

| German | English |
|---|---|
| Motorölverlust | Engine oil leak |
| Zündkerzen | Spark plugs |
| Turbolader | Turbocharger |
| Fahrwerk | Suspension/chassis |
| Elektronik | Electronics |
| Getriebe | Gearbox/transmission |
| Kupplung | Clutch |
| Bremsen | Brakes |
| Klimaanlage | Air conditioning |
| Undicht | Leaking / not sealing |
| Verschleiß | Wear |
| Ausfall | Failure |
| Pannen/1000 Fahrzeuge | Breakdowns per 1,000 vehicles |

> For production use, pass German text to your LLM with the translation prompt in the **Issue Patterns** section below.

---

## Smart Synthesis Patterns

### 1. One-sentence reliability verdict

Use this to generate a concise, attributable summary from the structured data:

```typescript
function reliabilityVerdict(
  make: string,
  model: string,
  year: number,
  r: ReliabilityYear
): string {
  const ratingEn = RATING_EN[r.rating] ?? r.rating;
  const genPart = r.generation_name ? ` (gen ${r.generation_name})` : "";
  const ct = r.class_thresholds;
  
  let classPart = "";
  if (ct) {
    // Find which threshold the vehicle falls at
    const val = r.breakdowns_per_1000;
    if (val <= ct.sehr_gut) {
      const pctBetter = (((ct.sehr_gut - val) / ct.sehr_gut) * 100).toFixed(0);
      classPart = ` — ${pctBetter}% below the segment's "Very Good" threshold of ≤${ct.sehr_gut}`;
    } else if (val <= ct.gut) {
      classPart = ` — within segment "Good" range (threshold ≤${ct.gut})`;
    } else {
      classPart = ` — above segment "Good" threshold of ${ct.gut}`;
    }
  }

  const mileage = r.annual_mileage_km
    ? ` (based on ${r.annual_mileage_km.toLocaleString()} km/year)`
    : "";

  return (
    `${make} ${model}${genPart}, ${year}: ` +
    `${r.breakdowns_per_1000} breakdowns per 1,000 vehicles — ` +
    `${ratingEn}${classPart}${mileage}. ` +
    `Source: ADAC Pannenstatistik.`
  );
}

// Example output:
// "BMW X3 (gen G01/F97), 2021: 1.4 breakdowns per 1,000 vehicles —
//  Very Good — 30% below the segment's "Very Good" threshold of ≤2.0
//  (based on 14,000 km/year). Source: ADAC Pannenstatistik."
```

### 2. Reliability trend (improving / stable / declining)

```typescript
function reliabilityTrend(years: ReliabilityYear[]): "improving" | "stable" | "declining" {
  if (years.length < 2) return "stable";
  const sorted = [...years].sort((a, b) => a.year - b.year);
  const first = sorted[0].rating_score;
  const last  = sorted[sorted.length - 1].rating_score;
  const delta = last - first;
  if (delta >  0.10) return "improving";  // rating_score went up = fewer breakdowns
  if (delta < -0.10) return "declining";
  return "stable";
}

// Display:
const trend = reliabilityTrend(vehicle_info.reliability_by_year);
const trendLabel = { improving: "improving ↑", stable: "stable →", declining: "declining ↓" }[trend];
```

### 3. Class comparison for a specific year

```typescript
function classComparison(r: ReliabilityYear): string | null {
  if (!r.class_thresholds) return null;
  const val = r.breakdowns_per_1000;
  const ct  = r.class_thresholds;

  // How far from the next threshold up?
  const segmentBest = ct.sehr_gut;
  const pct = (((segmentBest - val) / segmentBest) * 100).toFixed(0);
  const sign = val <= segmentBest ? `${pct}% better than` : `${Math.abs(+pct)}% worse than`;
  return `${sign} the segment's best class threshold (≤${segmentBest}/1,000)`;
}
```

### 4. Best year to buy (lowest breakdowns_per_1000)

```typescript
function bestModelYear(years: ReliabilityYear[]): ReliabilityYear | null {
  if (!years.length) return null;
  return years.reduce((best, r) =>
    r.breakdowns_per_1000 < best.breakdowns_per_1000 ? r : best
  );
}

const best = bestModelYear(vehicle_info.reliability_by_year);
// → { year: 2022, breakdowns_per_1000: 1.3, rating: "gut", ... }
```

### 5. LLM prompt to generate a full analysis

Once you have the structured data, you can ask your LLM to synthesise it into a user-facing answer. Pass the raw JSON, not raw German text:

```typescript
const systemPrompt = `You are an automotive expert. You receive structured ADAC reliability data.
Generate a clear, friendly analysis in English. 
Always cite "ADAC Pannenstatistik" as the data source.
Never invent numbers — use only the data provided.`;

const userPrompt = `
Vehicle: ${make} ${model}
ADAC reliability data:
${JSON.stringify(reliability_by_year, null, 2)}

Please provide:
1. A one-paragraph reliability summary
2. Which year had the best reliability and why
3. How this compares to its segment class (use class_thresholds)
4. Whether reliability is improving or declining
`;
```

---

## Displaying Issue Patterns

Issue patterns (`issue_patterns[]`) contain ADAC defect database entries in German. Translate them before display.

### LLM translation prompt

```typescript
async function translateIssuePatterns(patterns: IssuePattern[]): Promise<TranslatedPattern[]> {
  const response = await llm.complete({
    system: "You are a technical translator. Translate automotive defect data from German to English. Return JSON only.",
    user: `Translate these ADAC defect entries to English. Keep all technical terms precise.
Return a JSON array with the same structure, only translating: pattern_name, symptoms, root_cause, solution.
Input:
${JSON.stringify(patterns, null, 2)}`,
    response_format: { type: "json_object" }
  });
  return JSON.parse(response.content).patterns ?? patterns;
}
```

### Pattern card UI spec

```
┌─────────────────────────────────────────────────────┐
│ 🔧 Engine oil leak                  [medium]         │
│ ─────────────────────────────────────────────────── │
│ Symptom: Oil stains visible under the vehicle        │
│ Cause:   Oil pan gasket not sealing                  │
│ Fix:     Have the gasket replaced                    │
│                            Source: ADAC defect data  │
└─────────────────────────────────────────────────────┘
```

```typescript
const SEVERITY_BADGE: Record<string, string> = {
  low:      "bg-gray-100 text-gray-600",
  medium:   "bg-amber-100 text-amber-700",
  high:     "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};
```

---

## Car Image Display

```typescript
function VehicleImage({ vehicleInfo }: { vehicleInfo: ADACVehicleInfo }) {
  if (vehicleInfo.image_url) {
    return (
      <div>
        <img
          src={vehicleInfo.image_url}
          alt={`${vehicleInfo.make} ${vehicleInfo.model}`}
          style={{ width: "100%", borderRadius: 8, aspectRatio: "16/9", objectFit: "cover" }}
        />
        <p style={{ fontSize: 11, color: "#888", marginTop: 4 }}>
          © ADAC — <a href={vehicleInfo.adac_page_url} target="_blank">View on ADAC</a>
        </p>
      </div>
    );
  }

  // Fallback: styled placeholder with link
  return (
    <a href={vehicleInfo.adac_page_url} target="_blank"
       style={{ display: "block", background: "#1a1d2e", borderRadius: 8,
                padding: "32px 16px", textAlign: "center", textDecoration: "none" }}>
      <span style={{ fontSize: 48 }}>🚗</span>
      <p style={{ color: "#6366f1", marginTop: 8 }}>
        View {vehicleInfo.make} {vehicleInfo.model} on ADAC →
      </p>
    </a>
  );
}
```

**Image notes:**
- `image_url` is a 1500 × 844 px JPEG from the ADAC CDN (`assets.adac.de`)
- Always available for mainstream EU vehicles; may be `null` for very rare models
- When using the image, display the © ADAC attribution underneath
- `adac_page_url` always points to the canonical ADAC model page — link to it as "View on ADAC"

---

## ADAC Attribution

**Required attribution whenever you display reliability data or breakdown statistics:**

> *Data source: ADAC Pannenstatistik — Germany's largest annual vehicle breakdown survey.*

**Why attribution matters:**
- ADAC surveys millions of registered vehicles in Germany each year
- `breakdowns_per_1000` is a **measured statistic**, not an LLM estimate
- `class_thresholds` are segment-specific — the X3 is compared against other SUVs, not all cars
- The data has legal and journalistic weight; misattribution undermines user trust

**Suggested footer for any reliability widget:**

```tsx
<p style={{ fontSize: 11, color: "#666" }}>
  Reliability data: <a href="https://www.adac.de/rund-ums-fahrzeug/pannenstatistik/">
    ADAC Pannenstatistik
  </a> — annual breakdown survey of German-registered vehicles.
  Mileage assumption: {annualMileageKm?.toLocaleString()} km/year.
</p>
```

---

## Complete TypeScript Client

```typescript
// types.ts
export interface ClassThresholds {
  sehr_gut: number;
  gut: number;
  befriedigend: number;
  ausreichend: number;
}

export interface ReliabilityYear {
  year: number;
  breakdowns_per_1000: number;
  rating: string;            // German — translate with RATING_EN
  rating_score: number;      // 0.0–1.0, safe to use for comparisons
  generation_name: string | null;
  annual_mileage_km: number | null;
  class_thresholds: ClassThresholds | null;
}

export interface Generation {
  name: string | null;
  year_from: number | null;
  year_to: number | null;
}

export interface IssuePattern {
  pattern_name: string;      // German
  symptoms: string[];        // German
  root_cause: string;        // German
  solution: string;          // German
  severity: "low" | "medium" | "high" | "critical";
  affected_years: string | null;
}

export interface ADACVehicleInfo {
  make: string;
  model: string;
  year_from: number | null;
  year_to: number | null;
  description: string;
  image_url: string | null;          // ADAC vehicle photo, 1500 px JPEG
  adac_page_url: string;             // canonical ADAC page
  generations: Generation[];
  reliability_by_year: ReliabilityYear[];
}

export interface VehicleLookupResponse {
  normalized_make: string;
  normalized_model: string;
  year: number | null;
  corrections: string[];
  found: boolean;
  elapsed_ms: number;
  vehicle_info: ADACVehicleInfo | null;
  issue_patterns: IssuePattern[];
}

// client.ts
export async function lookupVehicle(
  model: string,
  make?: string,
  year?: number,
  baseUrl = ""
): Promise<VehicleLookupResponse> {
  const res = await fetch(`${baseUrl}/vehicle/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, make, year }),
  });
  if (!res.ok) throw new Error(`Vehicle lookup failed: ${res.status}`);
  return res.json();
}
```

---

## Example — Full Analysis Component (React)

```tsx
import { lookupVehicle, VehicleLookupResponse } from "./client";
import { RATING_EN, RATING_EMOJI } from "./translations";

function VehicleCard({ make, model, year }: { make: string; model: string; year?: number }) {
  const [data, setData] = React.useState<VehicleLookupResponse | null>(null);

  React.useEffect(() => {
    lookupVehicle(model, make, year).then(setData);
  }, [make, model, year]);

  if (!data || !data.found || !data.vehicle_info) return null;

  const vi = data.vehicle_info;
  const latestYear = vi.reliability_by_year.at(-1);

  return (
    <div className="vehicle-card">
      {/* Image */}
      {vi.image_url && (
        <img src={vi.image_url} alt={`${vi.make} ${vi.model}`} />
      )}

      {/* Header */}
      <h2>{vi.make} {vi.model}</h2>
      {data.corrections.length > 0 && (
        <p className="muted">Auto-corrected: {data.corrections.join(", ")}</p>
      )}

      {/* Reliability summary */}
      {latestYear && (
        <div className="reliability-badge">
          <span>{RATING_EMOJI[latestYear.rating]} </span>
          <strong>{RATING_EN[latestYear.rating]}</strong>
          <span> — {latestYear.breakdowns_per_1000}/1,000 vehicles ({latestYear.year})</span>
          {latestYear.class_thresholds && (
            <span className="muted">
              {" "}· segment "Very Good" threshold ≤{latestYear.class_thresholds.sehr_gut}
            </span>
          )}
        </div>
      )}

      {/* Generations */}
      <div className="generations">
        {vi.generations.map(g => (
          <span key={g.name} className="badge">
            {g.name} ({g.year_from}–{g.year_to ?? "present"})
          </span>
        ))}
      </div>

      {/* Issue patterns — send to LLM for translation before display */}
      {data.issue_patterns.length > 0 && (
        <details>
          <summary>Known issues ({data.issue_patterns.length})</summary>
          {/* translateIssuePatterns(data.issue_patterns) → display translated */}
        </details>
      )}

      {/* Attribution */}
      <p className="attribution">
        Reliability data: <a href={vi.adac_page_url} target="_blank">ADAC Pannenstatistik</a>
      </p>
    </div>
  );
}
```

---

## API Endpoint Summary

| Endpoint | Method | Purpose |
|---|---|---|
| `/vehicle/lookup` | POST | Structured ADAC data for a vehicle |
| `/image/analyze` | POST | Vision LLM analysis of a vehicle photo |
| `/chat` | POST | Full conversational automotive assistant |
| `/health` | GET | Service health check |

For Loveable's ADAC-only integration, **`/vehicle/lookup` is the only endpoint needed**.
