#!/usr/bin/env python
"""
Evaluation script — compares model responses against gold answers.

Usage:
    # Start the server first: uvicorn app.main:app --reload
    python scripts/run_eval.py [--base-url http://localhost:8000]

Output:
    Per-question pass/fail and overall score.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

_GOLD_PATH = Path(__file__).parent.parent / "data" / "gold_answers.jsonl"


async def evaluate(base_url: str) -> None:
    entries = [json.loads(l) for l in _GOLD_PATH.read_text().splitlines() if l.strip()]

    passed = 0
    total = len(entries)
    print(f"Running evaluation against {base_url} with {total} gold examples...\n")

    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        for entry in entries:
            payload = {"query": entry["query"]}
            if entry.get("vehicle"):
                payload["vehicle"] = entry["vehicle"]

            try:
                resp = await client.post("/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                answer = data.get("answer", "").lower()
                intent = data.get("intent", "")
                confidence = data.get("confidence", 0.0)

                # Simple keyword-match evaluation
                keywords = [k.lower() for k in entry.get("expected_answer_contains", [])]
                keyword_hits = sum(1 for k in keywords if k in answer)
                keyword_score = keyword_hits / len(keywords) if keywords else 1.0

                ok = keyword_score >= 0.5  # at least half of expected keywords
                passed += int(ok)

                status = "✓ PASS" if ok else "✗ FAIL"
                print(f"[{entry['id']}] {status}")
                print(f"  Query: {entry['query'][:70]}")
                print(f"  Confidence: {confidence:.2f}  Keywords: {keyword_hits}/{len(keywords)}")
                if not ok:
                    print(f"  Missing: {[k for k in keywords if k not in answer]}")
                    print(f"  Answer snippet: {answer[:150]}")
                print()

            except Exception as exc:
                print(f"[{entry['id']}] ✗ ERROR: {exc}\n")

    print(f"Result: {passed}/{total} passed ({passed/total*100:.0f}%)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(evaluate(args.base_url))


if __name__ == "__main__":
    main()
