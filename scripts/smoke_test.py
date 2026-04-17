#!/usr/bin/env python
"""
Smoke test — quick sanity check against a running server.

Usage:
    # Start the server first: uvicorn app.main:app --reload
    python scripts/smoke_test.py [--base-url http://localhost:8000]
"""
from __future__ import annotations

import asyncio
import sys
import argparse

import httpx


async def smoke_test(base_url: str) -> bool:
    ok = True
    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:

        # 1. Health check
        print("1. GET /health ...")
        resp = await client.get("/health")
        if resp.status_code == 200:
            print(f"   ✓ {resp.json()}")
        else:
            print(f"   ✗ status={resp.status_code}")
            ok = False

        # 2. Chat request
        print("2. POST /chat ...")
        resp = await client.post("/chat", json={
            "query": "Mein VW Golf 7 2017 macht ein Quietschgeräusch beim Bremsen",
            "vehicle": {"make": "VW", "model": "Golf", "year": 2017, "confidence": 0.9},
        })
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✓ answer={data['answer'][:80]!r}... confidence={data['confidence']:.2f}")
        else:
            print(f"   ✗ status={resp.status_code} body={resp.text[:200]}")
            ok = False

        # 3. Image analysis (no real image)
        print("3. POST /image/analyze ...")
        resp = await client.post("/image/analyze", data={
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Check_engine.svg/1200px-Check_engine.svg.png",
            "context": "Motorwarnleuchte",
        })
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✓ observations={data['observations'][:2]} confidence={data['confidence']:.2f}")
        else:
            print(f"   ✗ status={resp.status_code}")
            ok = False

        # 4. Debug graph
        print("4. GET /debug/graph ...")
        resp = await client.get("/debug/graph")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✓ nodes={data['nodes']}")
        else:
            print(f"   ✗ status={resp.status_code}")
            ok = False

    return ok


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    success = asyncio.run(smoke_test(args.base_url))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
