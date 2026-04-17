from __future__ import annotations

from typing import Any, Optional

from loguru import logger
from supabase import Client

from app.schemas.agent_outputs import SupabaseServiceCase, SupabaseWeakness
from app.schemas.common import VehicleInfo


class SupabaseRepository:
    """
    Typed read-only access to Supabase tables.

    All methods return empty lists / None when the client is unavailable,
    preventing the agent layer from needing to handle None clients directly.
    """

    def __init__(self, client: Optional[Client]) -> None:
        self.client = client

    def _available(self) -> bool:
        return self.client is not None

    async def get_vehicles_by_make_model(
        self,
        make: str,
        model: str,
        year: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        if not self._available():
            return []
        try:
            query = (
                self.client.table("vehicles")
                .select("*")
                .ilike("make", f"%{make}%")
                .ilike("model", f"%{model}%")
            )
            if year:
                query = query.eq("year", year)
            response = query.execute()
            return response.data or []
        except Exception as exc:
            logger.error(f"SupabaseRepository.get_vehicles_by_make_model error: {exc}")
            return []

    async def get_weaknesses_by_vehicle_id(
        self, vehicle_id: str
    ) -> list[SupabaseWeakness]:
        if not self._available():
            return []
        try:
            response = (
                self.client.table("weaknesses")
                .select("component, description, severity, source")
                .eq("vehicle_id", vehicle_id)
                .execute()
            )
            return [SupabaseWeakness(**row) for row in (response.data or [])]
        except Exception as exc:
            logger.error(f"SupabaseRepository.get_weaknesses_by_vehicle_id error: {exc}")
            return []

    async def get_issue_patterns(
        self,
        make: Optional[str] = None,
        model: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        if not self._available():
            return []
        try:
            query = self.client.table("issue_patterns").select("*")
            if make:
                query = query.contains("makes", [make])
            if model:
                query = query.contains("models", [model])
            response = query.limit(10).execute()
            return response.data or []
        except Exception as exc:
            logger.error(f"SupabaseRepository.get_issue_patterns error: {exc}")
            return []

    async def get_service_cases(
        self, vehicle_id: str, limit: int = 5
    ) -> list[SupabaseServiceCase]:
        if not self._available():
            return []
        try:
            response = (
                self.client.table("service_cases")
                .select("mileage, issue_type, resolution, cost_eur")
                .eq("vehicle_id", vehicle_id)
                .limit(limit)
                .execute()
            )
            return [SupabaseServiceCase(**row) for row in (response.data or [])]
        except Exception as exc:
            logger.error(f"SupabaseRepository.get_service_cases error: {exc}")
            return []

    async def get_demo_questions(self) -> list[dict[str, Any]]:
        if not self._available():
            return []
        try:
            response = self.client.table("demo_questions").select("*").limit(20).execute()
            return response.data or []
        except Exception as exc:
            logger.error(f"SupabaseRepository.get_demo_questions error: {exc}")
            return []

    async def vehicle_to_weaknesses(
        self, vehicle: VehicleInfo
    ) -> tuple[Optional[str], list[SupabaseWeakness]]:
        """Convenience: resolve vehicle_id from make/model, then fetch weaknesses."""
        vehicles = await self.get_vehicles_by_make_model(
            vehicle.make, vehicle.model, vehicle.year
        )
        if not vehicles:
            return None, []
        vehicle_id = vehicles[0]["id"]
        weaknesses = await self.get_weaknesses_by_vehicle_id(vehicle_id)
        return vehicle_id, weaknesses
