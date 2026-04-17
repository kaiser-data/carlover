"""
Evaluation service — logs query/response pairs for fine-tuning data collection.

This is a preparation layer only. No fine-tuning is implemented here.
Data is written to data/eval_log.jsonl for later annotation and fine-tuning.

When to use the collected data:
- After 200+ logged pairs, review for quality
- Annotate 50+ gold answers
- Run scripts/run_eval.py to measure model performance
- See README "Fine-Tuning Strategy" for next steps
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from loguru import logger

_LOG_PATH = Path("data/eval_log.jsonl")
_write_lock = asyncio.Lock()


class EvaluationService:
    """Async append-only logger for query/response evaluation pairs."""

    def __init__(self, log_path: Path = _LOG_PATH) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    async def log(
        self,
        request_id: str,
        query: str,
        vehicle: Optional[Any],
        intent: Optional[str],
        response: str,
        agent_results: dict[str, Any],
        confidence: float,
    ) -> None:
        record = {
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query": query,
            "vehicle": vehicle.model_dump() if vehicle and hasattr(vehicle, "model_dump") else None,
            "intent": intent,
            "response": response,
            "agent_results_keys": list(agent_results.keys()),
            "confidence": confidence,
            # Ground truth / gold answer: to be filled in manually
            "gold_answer": None,
            "gold_intent": None,
            "annotated": False,
        }
        async with _write_lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception as exc:
                logger.warning(f"EvaluationService failed to write: {exc}")


@lru_cache(maxsize=1)
def get_evaluation_service() -> EvaluationService:
    return EvaluationService()
