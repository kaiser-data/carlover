# CarLover 🚗

**AI-powered automotive assistant** — ask anything about your car, upload a photo, get real reliability data from ADAC and an intelligent diagnosis.

Built with [Loveable](https://loveable.dev) · Deployed on [Daytona](https://daytona.io) · Powered by [Featherless AI](https://featherless.ai)

---

## What it does

You type "My BMW 1er makes a noise when braking" — CarLover:

1. **Understands** your question (intent classification + entity extraction)
2. **Fetches real ADAC reliability data** — breakdown rates, known issues, class comparison
3. **Checks your service history** from Supabase
4. **Analyzes any photo** you attach (dashboard warning lights, damage)
5. **Runs a diagnostic script** in an isolated Daytona sandbox
6. **Synthesizes** everything into a clear, sourced answer

---

## Architecture

```
Loveable App  ──Ask──▶  Daytona Sandbox (FastAPI + LangGraph)
                  ◀──Answer──

Phase 1 · Sequential
  🎯 Classify Intent   →  📍 Extract Entities  →  ⚡ Route Agents

Phase 2 · Parallel (asyncio.gather)
  📊 ADAC Agent        →  live reliability data from adac.de
  🗄️  Database Agent   →  service history from Supabase
  📷 Image Agent       →  vision analysis via Qwen3-VL
  🔧 Sandbox Agent     →  diagnostic code in ephemeral Daytona sandbox

Phase 3 · Synthesis
  ✍️  Answer Agent     →  merges results, cites sources, Qwen2.5-72B
```

---

## Live Demo

**App:** [https://8000-2k20eipkhxqly8ze.daytonaproxy01.eu/ui/](https://8000-2k20eipkhxqly8ze.daytonaproxy01.eu/ui/)

**Vehicle lookup** (no auth needed):
```bash
curl -X POST https://8000-2k20eipkhxqly8ze.daytonaproxy01.eu/vehicle/lookup \
  -H "Content-Type: application/json" \
  -d '{"make": "BMW", "model": "3er", "year": 2020}'
```

---

## Quick Start

```bash
git clone https://github.com/kaiser-data/carlover
cd carlover
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add your API keys
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/ui/**

---

## API

### `POST /chat`
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "My VW Golf 7 2017 squeaks when braking"}'
```

### `POST /vehicle/lookup`
Typo-tolerant — `"Gollf"`, `"Polo"` without a brand, `"BMW 2er"` in the model field all work.
```bash
curl -X POST http://localhost:8000/vehicle/lookup \
  -H "Content-Type: application/json" \
  -d '{"model": "Golf", "year": 2019}'
```

Returns ADAC reliability data: breakdown rates per year, class thresholds, known issue patterns, generation name, and a direct vehicle photo URL.

### `POST /image/analyze`
```bash
curl -X POST http://localhost:8000/image/analyze \
  -F "image=@dashboard.jpg"
```

Detects warning lights, damage, and identifies the vehicle make/model. Auto-fetches ADAC data if the car is recognized.

---

## Key Features

**Typo-tolerant vehicle normalizer**
`"Vollkswagen Gollf"` → `VW Golf` · `"BMW 2er"` in the model field → correctly split · fuzzy matching via `difflib`

**Real ADAC data**
Scrapes the ADAC Autokatalog for live breakdown statistics, class-average thresholds, generation names, and issue patterns. Set `ADAC_PROVIDER=real` in `.env`.

**Vision analysis**
Qwen3-VL-30B via Featherless AI — identifies warning lights by name, detects visible damage, reads dashboards. If it recognizes the car, it enriches the response with ADAC data automatically.

**Ephemeral Daytona sandboxes**
The sandbox agent spins up a fresh isolated Python environment per diagnostic request via the Daytona SDK, runs the script, then deletes it — safe code execution with no blast radius.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Loveable (React) |
| Backend | FastAPI + LangGraph |
| LLMs | Featherless AI — Qwen2.5-72B, Qwen3-VL-30B |
| Database | Supabase (PostgreSQL) |
| Reliability data | ADAC Autokatalog (live scraping) |
| Sandbox execution | Daytona SDK |
| Deployment | Daytona cloud sandbox |

---

## Environment Variables

| Variable | Description |
|---|---|
| `FEATHERLESS_API_KEY` | Required — get one at featherless.ai |
| `FEATHERLESS_MODEL_ORCHESTRATOR` | Fast model for classification (default: Qwen2.5-14B) |
| `FEATHERLESS_MODEL_VISION` | Vision model (default: Qwen3-VL-30B) |
| `FEATHERLESS_MODEL_RESPONSE` | Synthesis model (default: Qwen2.5-72B) |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `ADAC_PROVIDER` | `real` or `mock` (default: `mock`) |
| `DAYTONA_API_KEY` | For sandbox agent + deployment |
| `DEBUG` | `true` to include per-node timing in responses |

---

## Deploy to Daytona

```bash
pip install daytona-sdk
python scripts/deploy_daytona.py            # deploy
python scripts/deploy_daytona.py --status   # check status
```

---

## Docs

- [`docs/daytona_overview.html`](docs/daytona_overview.html) — architecture diagram
- [`docs/loveable_adac_integration.md`](docs/loveable_adac_integration.md) — Loveable integration guide with German translation tables, TypeScript examples, and ADAC attribution
- [`docs/pitch.html`](docs/pitch.html) — 7-slide pitch deck

---

## License

MIT
