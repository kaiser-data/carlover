from __future__ import annotations

from typing import Optional

from app.providers.adac.base import ADACBaseProvider
from app.schemas.agent_outputs import (
    ADACIssuePattern,
    ADACServiceGuidance,
    ADACVehicleInfo,
)
from app.schemas.common import VehicleInfo

# ---------------------------------------------------------------------------
# Mock data — German market vehicles
# Replace or extend this dict when integrating a real data source.
# ---------------------------------------------------------------------------
_MOCK_VEHICLES: dict[tuple[str, str], ADACVehicleInfo] = {
    ("vw", "golf"): ADACVehicleInfo(
        make="VW",
        model="Golf",
        year_from=2012,
        year_to=2024,
        engine_types=["1.0 TSI", "1.5 TSI", "2.0 TDI", "GTI", "R"],
        known_issues_summary=(
            "DSG-Getriebe kann bei Kaltstart rucken (Bj. 2013–2017). "
            "Kühlmittelverlust durch undichte Ausgleichsbehälter-Deckel (1.4 TSI). "
            "Zahnriemenprobleme beim 2.0 TDI vor Inspektion."
        ),
    ),
    ("bmw", "3er"): ADACVehicleInfo(
        make="BMW",
        model="3er",
        year_from=2012,
        year_to=2023,
        engine_types=["318i", "320i", "330i", "318d", "320d", "330d", "M340i"],
        known_issues_summary=(
            "Ölverbrauch erhöht bei N20-Motor (320i). "
            "Kühlsystem-Thermostat kann ausfallen (F30-Generation). "
            "Steuerkette: Verschleiß möglich bei 318d/320d (N47-Motor)."
        ),
    ),
    ("mercedes", "c-klasse"): ADACVehicleInfo(
        make="Mercedes",
        model="C-Klasse",
        year_from=2014,
        year_to=2023,
        engine_types=["C180", "C200", "C220d", "C300", "C43 AMG"],
        known_issues_summary=(
            "Getriebesteuergerät defekt (7G-Tronic). "
            "AdBlue-System-Fehler bei Dieselmodellen. "
            "Elektrische Fensterheber-Probleme (W205)."
        ),
    ),
    ("audi", "a4"): ADACVehicleInfo(
        make="Audi",
        model="A4",
        year_from=2015,
        year_to=2023,
        engine_types=["1.4 TFSI", "2.0 TFSI", "2.0 TDI", "3.0 TDI", "S4"],
        known_issues_summary=(
            "Ölverlust am Kurbelwellenentlüfter (2.0 TFSI). "
            "DSG Probleme bei 7-Gang-Getriebe. "
            "Zündspulen können ausfallen (1.4/2.0 TFSI)."
        ),
    ),
    ("opel", "astra"): ADACVehicleInfo(
        make="Opel",
        model="Astra",
        year_from=2009,
        year_to=2023,
        engine_types=["1.2 Turbo", "1.4 Turbo", "1.6 CDTI", "2.0 CDTI"],
        known_issues_summary=(
            "Rost an Hinterachse (ältere Modelle). "
            "Infotainment-System friert ein (Astra K). "
            "Getriebeöl-Undichtigkeit (6-Gang Automatik)."
        ),
    ),
}

_MOCK_ISSUE_PATTERNS: list[ADACIssuePattern] = [
    ADACIssuePattern(
        pattern_name="Bremsquietschen",
        symptoms=["Quietschgeräusch beim Bremsen", "Schleifgeräusch", "Vibrieren beim Bremsen"],
        root_cause="Verschlissene Bremsbeläge oder Bremsscheiben. Ggf. Bremsabrieb auf Scheibe.",
        solution="Bremsbeläge und Scheiben prüfen, ggf. ersetzen. Richtlinie: alle 30.000–50.000 km.",
        severity="medium",
    ),
    ADACIssuePattern(
        pattern_name="Motorwarnleuchte",
        symptoms=["Motorwarnleuchte leuchtet", "CHECK ENGINE", "Motorkontrollleuchte"],
        root_cause="Vielschichtig: Lambdasonde, Zündkerze, AGR-Ventil, OBD-Fehlercode auslesen erforderlich.",
        solution="OBD-II Fehlerauslesung mit Diagnosegerät. Fehlercode ermitteln, gezielt beheben.",
        severity="high",
    ),
    ADACIssuePattern(
        pattern_name="Klimaanlage kühlt nicht",
        symptoms=["Klimaanlage kühlt nicht mehr", "Kältemittel verloren", "AC defekt"],
        root_cause="Kältemittelverlust durch undichte Leitungen oder Kompressorverschleiß.",
        solution="Kältemittel-Füllstand prüfen, Dichtheitsprüfung, ggf. Kompressor tauschen.",
        severity="low",
    ),
    ADACIssuePattern(
        pattern_name="Ruckeln beim Anfahren",
        symptoms=["Ruckeln beim Anfahren", "DSG-Ruckeln", "Getriebe schaltet hart"],
        root_cause="DSG-Mechatronik oder Kupplungsadaption. Häufig bei Kaltstart.",
        solution="DSG-Adaptierung zurücksetzen. Getriebeöl wechseln. Mechatronik prüfen.",
        severity="medium",
    ),
    ADACIssuePattern(
        pattern_name="Ölverlust",
        symptoms=["Ölfleck unter dem Auto", "Ölstand sinkt", "Ölgeruch"],
        root_cause="Undichte Ventildeckeldichtung, Kurbelwellenentlüfter oder Ölwannendichtung.",
        solution="Leckage lokalisieren, entsprechende Dichtung wechseln.",
        severity="high",
    ),
]

_MOCK_SERVICE: ADACServiceGuidance = ADACServiceGuidance(
    service_interval_km=15000,
    service_interval_months=12,
    typical_cost_eur=250.0,
    notes="Große Inspektion alle 30.000 km oder 24 Monate empfohlen. Zahnriemen-Wechsel je nach Hersteller.",
)


class MockADACProvider(ADACBaseProvider):
    """
    Mock ADAC provider with realistic German-market vehicle data.

    Source label: "ADAC Mock v1.0"

    To add a real provider:
    1. Create a new class inheriting ADACBaseProvider
    2. Implement the three abstract methods
    3. Set ADAC_PROVIDER=real in .env
    4. Register the class in app/api/deps.py
    """

    SOURCE_LABEL: str = "ADAC Mock v1.0"

    async def fetch_vehicle_info(self, vehicle: VehicleInfo) -> Optional[ADACVehicleInfo]:
        key = (vehicle.make.lower(), vehicle.model.lower())
        return _MOCK_VEHICLES.get(key)

    async def fetch_issue_patterns(
        self,
        vehicle: VehicleInfo,
        issue_keywords: Optional[list[str]] = None,
    ) -> list[ADACIssuePattern]:
        if not issue_keywords:
            return _MOCK_ISSUE_PATTERNS

        keywords_lower = [k.lower() for k in issue_keywords]
        results = []
        for pattern in _MOCK_ISSUE_PATTERNS:
            searchable = " ".join(
                [pattern.pattern_name] + pattern.symptoms + [pattern.root_cause]
            ).lower()
            if any(kw in searchable for kw in keywords_lower):
                results.append(pattern)
        return results or _MOCK_ISSUE_PATTERNS[:2]

    async def fetch_service_guidance(self, vehicle: VehicleInfo) -> ADACServiceGuidance:
        return _MOCK_SERVICE
