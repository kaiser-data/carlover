#!/usr/bin/env python
"""
Seed demo data into Supabase using the SQL files.

Usage:
    python scripts/seed_demo_data.py

Requires SUPABASE_URL and SUPABASE_KEY in .env or environment.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.providers.supabase.client import get_supabase_client


def main() -> None:
    client = get_supabase_client()
    if client is None:
        print("ERROR: Supabase client not available. Set SUPABASE_URL and SUPABASE_KEY.")
        sys.exit(1)

    schema_sql = (Path(__file__).parent.parent / "supabase" / "schema.sql").read_text()
    seed_sql = (Path(__file__).parent.parent / "supabase" / "seed.sql").read_text()

    print("Running schema.sql...")
    client.rpc("exec_sql", {"query": schema_sql}).execute()

    print("Running seed.sql...")
    client.rpc("exec_sql", {"query": seed_sql}).execute()

    print("Done. Demo data seeded successfully.")


if __name__ == "__main__":
    main()
