# Carlover — Automotive Assistant Backend

Production-near MVP multi-agent backend for an automotive assistant.
Handles vehicle diagnostics, known issues, service data, and image analysis.

---

## Architecture

```
FastAPI (HTTP)
    └── LangGraph StateGraph
            ├── intake → classify_intent → extract_entities
            ├── check_required_fields
            │     ├── [missing/ambiguous] → clarify_if_needed → END
            │     └── [ok]               → route_agents
            ├── route_agents → run_subagents (parallel)
            │     ├── ADAC Agent       (structured mock/real data)
            │     ├── Supabase Agent   (internal DB)
            │     └── Image Agent      (vision LLM)
            ├── merge_results
            ├── answer (synthesis LLM)
            └── finalize → ChatResponse
```

**Design principles:**
- Orchestrator = Router/Supervisor, not an autonomous agent
- Subagents = controlled workers with typed Pydantic outputs
- All LLM calls use `.with_structured_output(PydanticModel)`
- All model names read from ENV only
- Partial failure handling: one agent failing does not abort the pipeline
- Vehicle confidence scoring: ambiguous vehicles trigger clarification

---

## Agent Roles

| Agent | Role | Data Source |
|---|---|---|
| **Orchestrator** | Intent classification, entity extraction, routing | LLM (orchestrator model) |
| **ADAC Agent** | Vehicle info, issue patterns, service guidance | Mock (→ real) |
| **Supabase Agent** | Internal weaknesses, service cases, patterns | Supabase DB |
| **Image Agent** | Visual analysis of dashboard/damage photos | LLM (vision model) |
| **Answer Agent** | Synthesis of all results into user response | LLM (response model) |

---

## Setup

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Install

```bash
# Clone and enter project
cd carlover

# With uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Or with pip
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Configure

```bash
cp .env.example .env
# Edit .env — at minimum set:
# FEATHERLESS_API_KEY=your_key
# SUPABASE_URL=https://...
# SUPABASE_KEY=your_key
```

### Supabase Setup

1. Create a project at [supabase.com](https://supabase.com)
2. Run `supabase/schema.sql` in the SQL editor
3. Run `supabase/seed.sql` for demo data
4. Copy the project URL and service role key to `.env`

---

## Running

### Development

```bash
uvicorn app.main:app --reload --port 8000
```

### Docker

```bash
docker compose up --build
```

### Tests

```bash
pytest tests/ -v
```

### Smoke Test (requires running server)

```bash
python scripts/smoke_test.py
```

---

## API

### GET /health

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "version": "0.1.0", "timestamp": "..."}
```

### POST /chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Mein VW Golf 7 2017 macht ein Quietschgeräusch beim Bremsen",
    "vehicle": {"make": "VW", "model": "Golf", "year": 2017}
  }'
```

Response fields:
- `answer` — synthesized response in German
- `sources` — list of data sources used
- `confidence` — overall confidence score (0–1)
- `needs_clarification` — true if more info is needed
- `clarification_questions` — list of follow-up questions
- `used_agents` — which agents were invoked
- `debug_trace` — per-node timing (when DEBUG=true)
- `elapsed_ms` — total processing time

### POST /image/analyze

```bash
# By URL
curl -X POST http://localhost:8000/image/analyze \
  -F "image_url=https://example.com/dashboard.jpg" \
  -F "context=Dashboard Warnleuchten"

# By file upload
curl -X POST http://localhost:8000/image/analyze \
  -F "image=@/path/to/photo.jpg"
```

### GET /debug/graph

```bash
curl http://localhost:8000/debug/graph
```

Returns the full LangGraph node/edge structure as JSON.

---

## Vehicle Detection Confidence

The system scores vehicle identification confidence and handles ambiguity:

- `confidence >= 0.70`: proceed with best match
- `confidence < 0.70`: ask user for clarification
- Top-2 gap `< 0.20`: ask for disambiguation even with ok confidence

Thresholds are configurable via ENV:
```bash
VEHICLE_DETECTION_MIN_CONFIDENCE=0.70
VEHICLE_DETECTION_AMBIGUITY_GAP=0.20
```

---

## MCP Integration (Optional)

MCP (Model Context Protocol) tools are behind a feature flag:

```bash
MCP_ENABLED=true
```

To add a new MCP tool:
1. Implement the tool in `app/mcp/example_server.py`
2. Create an adapter in `app/mcp/adapters.py`
3. Register it in `app/mcp/registry.py`

See `app/mcp/example_server.py` for a template.

The app runs fully without MCP (`MCP_ENABLED=false`).

---

## Fine-Tuning Strategy

Fine-tuning is **not implemented** in this MVP. The infrastructure is prepared:

### What's in place
- `app/evaluation/evaluation_service.py` — logs every query/response pair to `data/eval_log.jsonl`
- `data/gold_answers.jsonl` — 5 curated gold examples
- `scripts/run_eval.py` — evaluates responses against gold answers

### When fine-tuning makes sense
1. After collecting **200+ logged query/response pairs**
2. After **manually annotating 50+ gold answers** (`gold_answer` field in eval_log)
3. After identifying **consistent failure patterns** in `run_eval.py` output
4. When the base model reliably fails on German automotive vocabulary or domain-specific reasoning

### Preparation steps (TODO)
1. Run the system in production for 2–4 weeks
2. Review `data/eval_log.jsonl`, annotate best answers as gold
3. Convert to fine-tuning format: `{"prompt": ..., "completion": ...}`
4. Upload to Featherless or Hugging Face for fine-tuning
5. Replace model names in `.env` with fine-tuned model IDs
6. Re-run `scripts/run_eval.py` to measure improvement

---

## Evaluation

```bash
# Start server
uvicorn app.main:app --reload

# Run evaluation against gold answers
python scripts/run_eval.py --base-url http://localhost:8000
```

Output: per-question pass/fail and overall score based on keyword matching.

---

## ENV Variables

| Variable | Default | Description |
|---|---|---|
| `FEATHERLESS_API_KEY` | required | Featherless AI API key |
| `FEATHERLESS_BASE_URL` | `https://api.featherless.ai/v1` | Featherless API base URL |
| `FEATHERLESS_MODEL_ORCHESTRATOR` | `Llama-3.1-8B-Instruct` | Fast model for classification |
| `FEATHERLESS_MODEL_REASONING` | `Llama-3.1-70B-Instruct` | Capable model for reasoning |
| `FEATHERLESS_MODEL_VISION` | `Qwen2-VL-7B-Instruct` | Vision-capable model |
| `FEATHERLESS_MODEL_RESPONSE` | `Llama-3.1-70B-Instruct` | Model for response synthesis |
| `SUPABASE_URL` | `""` | Supabase project URL |
| `SUPABASE_KEY` | `""` | Supabase service role key |
| `VEHICLE_DETECTION_MIN_CONFIDENCE` | `0.70` | Min confidence to proceed without clarification |
| `VEHICLE_DETECTION_AMBIGUITY_GAP` | `0.20` | Min gap between top-2 candidates |
| `ADAC_PROVIDER` | `mock` | `mock` or `real` |
| `MCP_ENABLED` | `false` | Enable MCP tool layer |
| `DEBUG` | `false` | Include debug trace in responses |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## Open TODOs

- [ ] Real ADAC data provider (replace mock)
- [ ] Authentication / API key middleware
- [ ] Session / conversation history in Supabase
- [ ] Streaming responses (SSE)
- [ ] Fine-tuning pipeline (see Fine-Tuning Strategy above)
- [ ] MCP tools: KBA recall database, EU recall lookup
- [ ] Rate limiting
- [ ] Supabase RLS policies for production
- [ ] CI/CD pipeline
