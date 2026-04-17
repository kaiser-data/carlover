# Carlover — Architecture & Agent Workflow

## Overview

Carlover is a multi-agent automotive assistant built on **LangGraph** and deployed on **Daytona**. A user request flows through an orchestration pipeline that classifies intent, extracts vehicle entities, runs specialist agents in parallel, and synthesizes a final answer.

---

## Daytona Deployment Workflow

```mermaid
flowchart TD
    subgraph Client["Client"]
        UI["Browser UI\n/ui/"]
        API_Client["API Consumer\ncurl / Loveable app"]
    end

    subgraph Daytona["Daytona Sandbox (python:3.12-slim)"]
        direction TB
        Server["FastAPI Server\nuvicorn :8000"]

        subgraph Routes["API Routes"]
            R1["POST /chat"]
            R2["POST /vehicle/lookup"]
            R3["POST /image/analyze"]
            R4["GET /health"]
        end

        subgraph Graph["LangGraph Pipeline"]
            N1["intake"]
            N2["classify_intent"]
            N3["extract_entities"]
            N4["check_required_fields"]
            N5{"needs\nclarification?"}
            N6["route_agents"]
            N7["run_subagents\n(parallel)"]
            N8["merge_results"]
            N9["answer"]
            N10["finalize"]
            N11["clarify_if_needed"]
        end

        subgraph Agents["Specialist Agents"]
            A1["ADAC Agent\nweb scraper"]
            A2["Supabase Agent\ninternal DB"]
            A3["Image Agent\nvision LLM"]
            A4["Sandbox Agent\ncode execution"]
        end

        subgraph External["External Services"]
            E1["Featherless AI\nQwen2.5 / Qwen3-VL"]
            E2["ADAC.de\nautokatalog"]
            E3["Supabase\nPostgres"]
            E4["Daytona API\nsandbox mgmt"]
        end
    end

    UI --> Server
    API_Client --> Server
    Server --> Routes
    R1 --> N1
    R2 --> A1
    R3 --> A3

    N1 --> N2 --> N3 --> N4 --> N5
    N5 -->|"yes"| N11
    N5 -->|"no"| N6
    N6 --> N7
    N7 --> A1 & A2 & A3 & A4
    A1 & A2 & A3 & A4 --> N8
    N8 --> N9 --> N10

    A1 --> E2
    A3 --> E1
    N2 --> E1
    N3 --> E1
    N9 --> E1
    A2 --> E3
    A4 --> E4
```

---

## Agent Descriptions

| Agent | Trigger | What it does |
|---|---|---|
| **ADAC Agent** | `diagnosis`, `lookup`, always for `/vehicle/lookup` | Scrapes adac.de autokatalog, extracts JSON hydration data, returns all generations + year-by-year Pannenstatistik + defect patterns |
| **Supabase Agent** | `diagnosis`, `lookup` | Queries internal Postgres for vehicle weaknesses and past service cases |
| **Image Agent** | Any request with `image_url`, or `image_analysis` intent | Vision LLM analyzes photo → observations, warning lights, damage; auto-fetches ADAC data if vehicle is identified |
| **Sandbox Agent** | `code_execution` intent or `diagnosis` with vehicle | Spins up a Daytona ephemeral sandbox, runs diagnostic Python, returns output |

---

## Intent → Agent Routing

```mermaid
flowchart LR
    Q["User query"] --> ORC["Orchestrator\nclassify_intent\nextract_entities"]

    ORC -->|"diagnosis + vehicle"| P1["adac + supabase + sandbox"]
    ORC -->|"diagnosis (no vehicle)"| P2["adac"]
    ORC -->|"lookup"| P3["adac + supabase"]
    ORC -->|"image_analysis"| P4["image"]
    ORC -->|"code_execution"| P5["sandbox"]
    ORC -->|"general"| P6["adac"]

    P1 & P2 & P3 & P4 & P5 & P6 --> ANS["Answer Agent\nsynthesize response"]
```

---

## Vehicle Lookup Flow (fuzzy matching)

```mermaid
flowchart TD
    IN["Input: make (optional), model, year"] 
    IN --> NRM["vehicle_normalizer.py\n• Strip 'Series' suffix\n• Infer make from model\n• Fuzzy-correct typos\n  (difflib cutoff 0.60)"]
    NRM --> SLUG["real_provider._slugify()\n• BMW 3er → 3er-reihe\n• C-Klasse → c-klasse\n• VW → vw"]
    SLUG --> ADAC["GET adac.de/autokatalog\n/{make}/{model}/"]
    ADAC --> PARSE["Extract window.__staticRouterHydrationData\n→ rangePage JSON"]
    PARSE --> OUT["VehicleLookupResponse\n• All generations\n• Reliability by year\n• All defect patterns"]
```

---

## Image Analysis Flow

```mermaid
flowchart TD
    IMG["Image URL or file upload"]
    IMG --> VIS["Vision LLM\nQwen3-VL-30B"]
    VIS --> RES["ImageAnalysisResult\n• observations\n• warning_lights\n• damage_detected\n• image_quality\n• vehicle_count\n• detected_make / detected_model"]
    RES -->|"vehicle identified"| ADAC2["ADAC lookup\n(parallel fetch)"]
    RES -->|"multiple vehicles"| CLQ["clarification_question\n(model describes each car)"]
    RES -->|"unusable quality"| CLQ2["clarification_question\n'please retake photo'"]
    ADAC2 --> ENRICH["Enriched response\n+ adac_summary\n+ adac_issue_patterns"]
```

---

## Key Design Decisions

- **Parallel agents** — `asyncio.gather(return_exceptions=True)` so one agent failure doesn't abort the pipeline
- **Fuzzy matching** — `difflib.get_close_matches` with 0.60 cutoff handles typos; `MODEL_TO_BRAND` handles brand-less input
- **ADAC scraping** — extracts embedded JSON (`window.__staticRouterHydrationData`) from server-rendered pages; 24h in-memory cache; 1s rate-limit delay
- **LLM structured output** — all LLM calls use `method="json_mode"` (required for Featherless/vLLM backend)
- **Daytona** — each deployment creates a new sandbox; the Sandbox Agent creates ephemeral 5-minute sandboxes for code execution
