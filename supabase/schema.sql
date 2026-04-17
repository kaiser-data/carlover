-- Carlover Supabase Schema
-- Run this in the Supabase SQL editor or with psql.

-- ------------------------------------------------------------------ --
-- vehicles
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS vehicles (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    make         TEXT NOT NULL,
    model        TEXT NOT NULL,
    year         INTEGER,
    engine       TEXT,
    transmission TEXT,
    fuel_type    TEXT,
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vehicles_make_model ON vehicles (make, model);

-- ------------------------------------------------------------------ --
-- weaknesses
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS weaknesses (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id  UUID REFERENCES vehicles(id) ON DELETE CASCADE,
    component   TEXT NOT NULL,
    description TEXT NOT NULL,
    severity    TEXT CHECK (severity IN ('low','medium','high','critical')),
    source      TEXT DEFAULT 'internal',
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weaknesses_vehicle_id ON weaknesses (vehicle_id);

-- ------------------------------------------------------------------ --
-- service_cases
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS service_cases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_id  UUID REFERENCES vehicles(id) ON DELETE CASCADE,
    mileage     INTEGER,
    issue_type  TEXT,
    resolution  TEXT,
    cost_eur    NUMERIC(10, 2),
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_service_cases_vehicle_id ON service_cases (vehicle_id);

-- ------------------------------------------------------------------ --
-- issue_patterns  (cross-vehicle, array-based vehicle matching)
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS issue_patterns (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    makes        TEXT[]   DEFAULT '{}',
    models       TEXT[]   DEFAULT '{}',
    pattern_name TEXT NOT NULL,
    symptoms     TEXT[]   DEFAULT '{}',
    root_cause   TEXT,
    solution     TEXT,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- ------------------------------------------------------------------ --
-- demo_questions  (for evaluation and smoke testing)
-- ------------------------------------------------------------------ --
CREATE TABLE IF NOT EXISTS demo_questions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question             TEXT NOT NULL,
    expected_intent      TEXT,
    vehicle_json         JSONB,
    ground_truth_answer  TEXT,
    created_at           TIMESTAMPTZ DEFAULT now()
);
