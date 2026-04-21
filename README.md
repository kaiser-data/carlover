# CarLover 🚗

A multi-agent automotive assistant. Ask a natural-language question about your car, optionally upload a photo, and get a sourced diagnosis backed by live ADAC reliability data, your own service history, and a vision pipeline.

**Live demo:** https://8000-bfa16ffa-8c1c-45c1-91b5-ae17fbd72b23.daytonaproxy01.eu/ui/
**API base:** same host, no `/ui/` suffix. OpenAPI at `/docs`, ReDoc at `/redoc`.

---

## What it does

Type *"My BMW 1er 2020 squeaks when I brake"*, optionally drag in a dashboard photo, and the backend:

1. Classifies intent and extracts `{make, model, year, variant}` with typo-tolerant matching.
2. Runs up to four specialist agents in parallel (ADAC, Supabase, Image, Sandbox).
3. Merges the results and synthesises a German-language answer with citations, confidence, and follow-up questions when data is incomplete.

If the image has multiple cars the UI shows clarification cards with bounding boxes; if the inferred make/model is ambiguous the pipeline asks rather than guesses.

---

## Architecture

```
            ┌─────────────────────────────────────────────────┐
            │  FastAPI app (lifespan warms HF models,         │
            │  serves /ui static, mounts /chat /vehicle/...)  │
            └─────────────────────────────────────────────────┘
                                   │
                                   ▼
                         ┌─────────────────┐
                         │  LangGraph      │
                         │  StateGraph     │
                         └─────────────────┘
                                   │
  intake ─► classify_intent ─► extract_entities ─► check_required_fields
                                                           │
                         needs_clarification?  ─── yes ──► clarify_if_needed ─► finalize
                                                           │ no
                                                           ▼
                                                     route_agents
                                                           │
                                                           ▼
                                     ┌─────────────────────────────────────┐
                                     │ run_subagents (asyncio.gather)       │
                                     ├─────────────────────────────────────┤
                                     │  adac_agent       ADAC Autokatalog   │
                                     │  supabase_agent   service history    │
                                     │  image_agent      HF + VLM hybrid    │
                                     │  sandbox_agent    Daytona ephemeral  │
                                     └─────────────────────────────────────┘
                                                           │
                                                           ▼
                                       merge_results ─► answer ─► finalize
```

Each box maps directly to a file:

| Stage                | File                                       |
|---|---|
| Intake / graph nodes | `app/graph/nodes.py`, `app/graph/graph.py` |
| Intent / entities    | `app/agents/orchestrator_agent.py`         |
| ADAC                 | `app/agents/adac_agent.py`, `app/providers/adac/*` |
| Supabase             | `app/agents/supabase_agent.py`, `app/providers/supabase/*` |
| Image                | `app/agents/image_agent.py`, `app/services/car_detection.py` |
| Sandbox              | `app/agents/sandbox_agent.py`, `app/providers/daytona/*`  |
| Answer synthesis     | `app/agents/answer_agent.py`               |
| LLM routing          | `app/providers/llm/model_router.py`        |

### Image pipeline (hybrid)

The image agent runs **two paths concurrently** and merges them:

- **Path A — HuggingFace Inference API** (deterministic, source of truth for identity)
  - `facebook/detr-resnet-50` → car count + bounding boxes
  - `dima806/car_models_image_detection` → make/model (369 classes, only called when DETR returns exactly one car)
- **Path B — Featherless Qwen3-VL-235B-A22B-Thinking** (enrichment)
  - Damage detection, warning-light names, prose observations, image-quality check

Either path can fail and the response still renders. A tiny white PNG is fired at both HF models on app startup (`lifespan` in `app/main.py`) so the first real request is warm.

### ADAC pipeline (three-tier fetch)

Daytona sandboxes have a restrictive outbound allowlist — `adac.de` is blocked. `app/providers/adac/real_provider.py:_fetch_page` therefore tries, in order:

1. **Supabase Edge Function** (`supabase/functions/adac-proxy/index.ts`) — always reachable from Daytona because the sandbox can talk to its own Supabase project. Enforces a host allowlist (`www.adac.de` only) at the edge.
2. **ScraperAPI proxy** (when `SCRAPER_API_KEY` is set) — fallback for non-Daytona environments.
3. **Direct fetch** — works from a developer laptop, blocked from the Daytona sandbox.

Parsing is identical in all three cases: extract `window.__staticRouterHydrationData`, navigate to `rangePage`, map to `ADACVehicleInfo` + `ADACIssuePattern[]`.

---

## Repository layout

```
app/
  agents/            # one module per specialist agent
  api/routes/        # FastAPI route handlers (health, chat, image, vehicle, debug)
  graph/             # LangGraph state, nodes, and compiled graph
  providers/         # adac/, daytona/, llm/, supabase/ — external I/O only
  schemas/           # shared Pydantic models (requests, responses, vehicle, image)
  services/          # car_detection.py — HF Inference API client
  utils/             # vehicle_normalizer, etc.
  main.py            # FastAPI app factory, lifespan, /ui static mount
frontend/
  index.html         # single-file vanilla HTML/CSS/JS UI, mounted at /ui/
supabase/
  functions/adac-proxy/index.ts  # Deno edge function for ADAC scraping
  schema.sql, seed.sql           # DB schema + seed
scripts/
  deploy_daytona.py  # create/stop/status a Daytona sandbox
  smoke_test.py      # end-to-end request against a running instance
  run_eval.py        # replay eval_log.jsonl for regressions
  seed_demo_data.py  # populate Supabase with demo rows
tests/               # pytest suite — see Tests section
docs/                # architecture.md + auxiliary HTML
```

---

## Backend API

Five JSON endpoints, all CORS-open (`Access-Control-Allow-Origin: *`). Interactive docs at `/docs` (Swagger) and `/redoc`.

Set `BASE` to either the live demo URL or `http://localhost:8000` for the examples below.

### `GET /health`

```json
{ "status": "ok", "version": "0.1.0", "timestamp": "2026-04-21T08:03:25Z" }
```

### `POST /chat`

Runs the full LangGraph pipeline.

**Request**
```ts
{
  query: string;                          // 1–2000 chars
  vehicle?: { make: string; model: string; year?: number; variant?: string; vin?: string };
  image_url?: string;                     // http(s) URL or data:image/...;base64,...
  session_id?: string;                    // optional, for multi-turn conversations
}
```

**Response**
```ts
{
  request_id: string;
  answer: string;                         // synthesized German-language answer
  sources: Array<{ label: string; type: "adac"|"supabase"|"image"|"internal"; confidence: number; url?: string }>;
  confidence: number;                     // 0–1
  needs_clarification: boolean;
  clarification_questions: string[];
  used_agents: string[];                  // ["adac","database","image","sandbox"]
  debug_trace: Array<{ node: string; elapsed_ms: number; note?: string }>;  // only when DEBUG=true
  elapsed_ms: number;
  uncertainty_notes: string[];
}
```

```bash
curl -X POST $BASE/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"My VW Golf 7 2017 squeaks when braking"}'
```

### `POST /vehicle/lookup`

Typo-tolerant ADAC lookup — `"Vollkswagen Gollf"` → VW Golf · `"Polo"` alone → VW Polo · `"BMW 2er"` in the model field → split correctly.

**Request**
```ts
{ make?: string; model: string; year?: number }  // model required, min length 1
```

**Response**
```ts
{
  normalized_make: string;
  normalized_model: string;
  year?: number;
  corrections: string[];                  // human-readable inference/typo log
  vehicle_info?: {
    known_issues_summary?: string;
    reliability_by_year?: Array<{ year: number; breakdowns_per_1000: number; rating: string; rating_score: number; generation_name?: string }>;
    generations?: Array<{ name: string; year_from: number; year_to?: number }>;
    image_url?: string;
    adac_page_url?: string;
  };
  issue_patterns: Array<{
    pattern_name: string;
    symptoms: string[];
    root_cause: string;
    solution: string;
    severity?: "low"|"medium"|"high";
    affected_years?: string;
  }>;
  found: boolean;                         // true when vehicle_info is populated
  elapsed_ms: number;
}
```

```bash
curl -X POST $BASE/vehicle/lookup \
  -H "Content-Type: application/json" \
  -d '{"model":"Golf","year":2019}'
```

### `POST /image/analyze`

Accepts either a URL/data-URI (form field) or a file upload (multipart).

**Request (multipart or urlencoded)**
- `image_url` *(string, optional)* — `http(s)://…` or `data:image/jpeg;base64,…`
- `image` *(file, optional)* — alternative to `image_url`
- `context` *(string, optional)* — e.g. `"dashboard warning lights"`

**Response**
```ts
{
  request_id: string;
  observations: string[];
  possible_findings: string[];
  warning_lights_detected: string[];      // e.g. ["engine_warning","oil_pressure"]
  damage_detected: boolean;
  limitations: string[];
  confidence: number;                     // 0–1
  raw_description?: string;
  vehicle_detected: boolean;
  vehicle_count: number;
  image_quality: "good"|"poor"|"unusable";
  needs_clarification: boolean;
  clarification_questions: string[];
  detected_make?: string;                 // from HF dima806 classifier
  detected_model?: string;
  vehicle_boxes: Array<{ label: string; x1: number; y1: number; x2: number; y2: number; confidence: number }>;  // 0–1 normalized
  image_rotation_deg: 0|90|180|270;
  adac_summary?: string;                  // auto-fetched when make/model resolved
  adac_issue_patterns?: object[];
  elapsed_ms: number;
}
```

```bash
# File upload
curl -X POST $BASE/image/analyze -F "image=@dashboard.jpg"

# URL
curl -X POST $BASE/image/analyze \
  -F "image_url=https://example.com/car.jpg" \
  -F "context=front bumper damage"
```

### `GET /debug/graph`

Returns the compiled LangGraph structure for visualization.

```ts
{ nodes: string[]; edges: Array<{ from: string; to: string; condition?: string }>; entry_point?: string }
```

---

## Frontend integration

Minimal TypeScript client:

```ts
const BASE = "https://8000-bfa16ffa-8c1c-45c1-91b5-ae17fbd72b23.daytonaproxy01.eu";

async function chat(query: string, image_url?: string) {
  const r = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, image_url }),
  });
  return r.json();
}

async function lookup(model: string, year?: number, make?: string) {
  const r = await fetch(`${BASE}/vehicle/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model, year, make }),
  });
  return r.json();
}

async function analyzeImage(file: File, context?: string) {
  const form = new FormData();
  form.append("image", file);
  if (context) form.append("context", context);
  const r = await fetch(`${BASE}/image/analyze`, { method: "POST", body: form });
  return r.json();
}
```

Typical UI wiring:

- **Chat box + optional drop zone** → `POST /chat`. Render `answer`, show `sources` as pills, turn `clarification_questions` into buttons that re-submit the selected clarification.
- **Standalone lookup widget** → `POST /vehicle/lookup`. Render `vehicle_info.reliability_by_year` as a bar chart; list `issue_patterns` as expandable cards.
- **Image analysis panel** → `POST /image/analyze`. Overlay `vehicle_boxes` on the uploaded image; render `warning_lights_detected` as badges.

Error handling: all endpoints return HTTP 200 on degraded outcomes — check `confidence`, `found`, `limitations`, and `uncertainty_notes` in the body. HTTP 4xx/5xx indicate protocol-level failures.

The repo ships with a reference frontend at `frontend/index.html` (~1400 lines of vanilla HTML/CSS/JS, no build step). The FastAPI app mounts it at `/ui/`, so the live demo URL and the API URL are the same origin.

---

## Quick start (local)

```bash
git clone https://github.com/kaiser-data/carlover
cd carlover
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env                      # fill in API keys
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/ui/ in a browser.

Requires Python ≥ 3.12.

---

## Deployment

### Daytona sandbox (backend)

```bash
pip install daytona-sdk
python3 scripts/deploy_daytona.py             # create + upload + start
python3 scripts/deploy_daytona.py --status    # show state + preview URL
python3 scripts/deploy_daytona.py --stop      # stop the current sandbox
```

The script reads `.env`, creates a **public** Daytona sandbox with `auto_stop_interval=0`, uploads the project tree, `pip install`s runtime deps, starts `uvicorn` in a background session, and writes the sandbox ID to `.daytona_sandbox_id`. The preview URL printed at the end is the UUID-form public URL (e.g. `https://8000-<uuid>.daytonaproxy01.eu`); the signed short URL is also printed but not needed for public access.

### Supabase Edge Function (ADAC proxy)

Required when `ADAC_PROVIDER=real` and the backend is hosted on Daytona — the sandbox can't reach `adac.de` directly.

```bash
brew install supabase/tap/supabase        # or equivalent
export SUPABASE_ACCESS_TOKEN=sbp_...      # from supabase.com/dashboard/account/tokens
supabase functions deploy adac-proxy \
  --project-ref <your-project-ref> --no-verify-jwt
```

The function is ~60 lines of Deno (`supabase/functions/adac-proxy/index.ts`), rejects any host other than `www.adac.de`, and adds a 1-hour public cache header. Supabase's free tier allows 500K invocations/month.

### Docker (alternative)

```bash
docker compose up --build
```

Serves on `localhost:8000` with the same env-var contract.

---

## Environment variables

| Variable | Required? | Notes |
|---|---|---|
| `LLM_PROVIDER` | yes | `groq` (default) or `featherless` — both OpenAI-compatible |
| `GROQ_API_KEY` | when `LLM_PROVIDER=groq` | |
| `FEATHERLESS_API_KEY` | when `LLM_PROVIDER=featherless` | |
| `GROQ_MODEL_*` / `FEATHERLESS_MODEL_*` | no | Per-task overrides: `ORCHESTRATOR`, `REASONING`, `VISION`, `RESPONSE` |
| `HUGGINGFACE_API_KEY` | no | Enables HF DETR + dima806 classifier. Empty = VLM-only. |
| `HF_DETECTION_MODEL` / `HF_CLASSIFICATION_MODEL` | no | Override default HF model IDs |
| `SUPABASE_URL` / `SUPABASE_KEY` | yes | Service-role JWT. Also used by the ADAC edge-function proxy. |
| `SUPABASE_ACCESS_TOKEN` | deploy-only | `sbp_…` token, used solely by `supabase functions deploy` |
| `ADAC_PROVIDER` | yes | `real` (scrape) or `mock` (bundled fixtures) |
| `SCRAPER_API_KEY` | no | Optional middle fallback between Supabase proxy and direct fetch |
| `DAYTONA_API_KEY` | yes | Needed by the sandbox agent and the deploy script |
| `DAYTONA_API_URL` | no | Defaults to `https://app.daytona.io/api` |
| `DEBUG` | no | `true` → include per-node timing in `/chat` responses |
| `LOG_LEVEL` | no | `INFO` default |

---

## Tests

```bash
pytest                       # full suite
pytest tests/test_image_detection.py -v  # single file
```

Suite covers:
- `test_health.py` — liveness + graph compile smoke
- `test_chat_flow.py` — end-to-end chat with mocked LLM
- `test_graph_routing.py` — clarification vs. run_subagents branch
- `test_image_detection.py` — vehicle count, multi-car, warning lights, rotation, no-vehicle, **HF hybrid path**, brand/model splitter
- `test_image_flow.py` — `/image/analyze` request/response
- `test_adac_agent.py` — real-provider parsing fixtures + keyword filtering
- `test_supabase_agent.py` — service-history agent against a mocked client

No network calls in CI — all external providers are mocked.

---

## License

MIT.
