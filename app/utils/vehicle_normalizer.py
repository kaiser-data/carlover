"""
Vehicle name normalization utilities.

Handles:
- Brand-less model input  ("Polo"        → VW Polo)
- Typos in make           ("Vollkswagen" → Volkswagen)
- Typos in model          ("Gollf"       → Golf via close-match)
- Mixed-up make/model     ("Golf" as make with no model → VW Golf)
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

# model_lower → canonical make
MODEL_TO_BRAND: dict[str, str] = {
    # Volkswagen
    "golf": "VW", "polo": "VW", "passat": "VW", "tiguan": "VW",
    "touareg": "VW", "arteon": "VW", "t-roc": "VW", "t-cross": "VW",
    "id.3": "VW", "id.4": "VW", "id.5": "VW", "id.6": "VW",
    "sharan": "VW", "touran": "VW", "caddy": "VW", "transporter": "VW",
    # Audi
    "a1": "Audi", "a3": "Audi", "a4": "Audi", "a5": "Audi",
    "a6": "Audi", "a7": "Audi", "a8": "Audi",
    "q2": "Audi", "q3": "Audi", "q5": "Audi", "q7": "Audi", "q8": "Audi",
    "tt": "Audi", "r8": "Audi", "e-tron": "Audi",
    # BMW
    "1er": "BMW", "2er": "BMW", "3er": "BMW", "4er": "BMW",
    "5er": "BMW", "6er": "BMW", "7er": "BMW", "8er": "BMW",
    "x1": "BMW", "x2": "BMW", "x3": "BMW", "x4": "BMW",
    "x5": "BMW", "x6": "BMW", "x7": "BMW",
    "i3": "BMW", "i4": "BMW", "i7": "BMW", "ix": "BMW",
    # Mercedes-Benz
    "a-klasse": "Mercedes-Benz", "b-klasse": "Mercedes-Benz",
    "c-klasse": "Mercedes-Benz", "e-klasse": "Mercedes-Benz",
    "s-klasse": "Mercedes-Benz", "cla": "Mercedes-Benz",
    "gla": "Mercedes-Benz", "glb": "Mercedes-Benz",
    "glc": "Mercedes-Benz", "gle": "Mercedes-Benz", "gls": "Mercedes-Benz",
    "eqc": "Mercedes-Benz", "eqa": "Mercedes-Benz",
    # Opel / Vauxhall
    "corsa": "Opel", "astra": "Opel", "insignia": "Opel",
    "mokka": "Opel", "grandland": "Opel", "crossland": "Opel",
    # Ford
    "fiesta": "Ford", "focus": "Ford", "kuga": "Ford",
    "puma": "Ford", "mondeo": "Ford", "mustang": "Ford", "explorer": "Ford",
    # Renault
    "clio": "Renault", "megane": "Renault", "kadjar": "Renault",
    "captur": "Renault", "zoe": "Renault", "arkana": "Renault",
    # Peugeot
    "108": "Peugeot", "208": "Peugeot", "308": "Peugeot",
    "408": "Peugeot", "508": "Peugeot",
    "2008": "Peugeot", "3008": "Peugeot", "5008": "Peugeot",
    # Toyota
    "yaris": "Toyota", "corolla": "Toyota", "camry": "Toyota",
    "rav4": "Toyota", "highlander": "Toyota", "land cruiser": "Toyota",
    "aygo": "Toyota", "c-hr": "Toyota", "prius": "Toyota",
    # Honda
    "civic": "Honda", "accord": "Honda", "jazz": "Honda",
    "cr-v": "Honda", "hr-v": "Honda", "e": "Honda",
    # Škoda
    "fabia": "Škoda", "octavia": "Škoda", "superb": "Škoda",
    "karoq": "Škoda", "kodiaq": "Škoda", "scala": "Škoda",
    # Seat / Cupra
    "ibiza": "Seat", "leon": "Seat", "ateca": "Seat",
    "tarraco": "Seat", "arona": "Seat",
    # Hyundai
    "i10": "Hyundai", "i20": "Hyundai", "i30": "Hyundai",
    "tucson": "Hyundai", "santa fe": "Hyundai", "kona": "Hyundai",
    "ioniq": "Hyundai", "ioniq 5": "Hyundai", "ioniq 6": "Hyundai",
    # Kia
    "picanto": "Kia", "rio": "Kia", "ceed": "Kia",
    "sportage": "Kia", "sorento": "Kia", "stonic": "Kia",
    "niro": "Kia", "ev6": "Kia",
    # Nissan
    "micra": "Nissan", "juke": "Nissan", "qashqai": "Nissan",
    "x-trail": "Nissan", "leaf": "Nissan", "ariya": "Nissan",
    # Mazda
    "mazda2": "Mazda", "mazda3": "Mazda", "mazda6": "Mazda",
    "cx-3": "Mazda", "cx-5": "Mazda", "cx-30": "Mazda", "mx-5": "Mazda",
    # Volvo
    "v40": "Volvo", "v60": "Volvo", "v90": "Volvo",
    "s60": "Volvo", "s90": "Volvo",
    "xc40": "Volvo", "xc60": "Volvo", "xc90": "Volvo",
    # Fiat
    "500": "Fiat", "500x": "Fiat", "500l": "Fiat",
    "panda": "Fiat", "tipo": "Fiat", "punto": "Fiat",
    # Citroën
    "c1": "Citroën", "c3": "Citroën", "c4": "Citroën",
    "c5": "Citroën", "berlingo": "Citroën",
    # Dacia
    "sandero": "Dacia", "duster": "Dacia", "jogger": "Dacia",
    "spring": "Dacia", "logan": "Dacia",
}

KNOWN_MAKES: list[str] = [
    "VW", "Volkswagen", "Audi", "BMW", "Mercedes-Benz", "Mercedes",
    "Opel", "Ford", "Renault", "Peugeot", "Citroën", "Toyota", "Honda",
    "Škoda", "Skoda", "Seat", "Cupra", "Hyundai", "Kia", "Nissan",
    "Mazda", "Volvo", "Fiat", "Dacia", "Porsche", "Lamborghini",
    "Ferrari", "Alfa Romeo", "Lancia", "Jeep", "Chrysler", "Dodge",
    "Chevrolet", "Tesla", "Subaru", "Mitsubishi", "Suzuki", "Mini",
    "Land Rover", "Jaguar", "Bentley", "Rolls-Royce", "Maserati",
]

# English name → ADAC-compatible (German) model name
# ADAC URLs use German naming: 1er, 3er, A-Klasse — not "1 Series", "A Class"
_MODEL_ALIASES: dict[str, str] = {
    "1 series": "1er",
    "2 series": "2er",
    "3 series": "3er",
    "4 series": "4er",
    "5 series": "5er",
    "6 series": "6er",
    "7 series": "7er",
    "8 series": "8er",
    "a class": "A-Klasse",
    "b class": "B-Klasse",
    "c class": "C-Klasse",
    "e class": "E-Klasse",
    "s class": "S-Klasse",
    "g class": "G-Klasse",
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class NormalizedVehicle:
    make: str
    model: str
    year: Optional[int] = None
    corrections: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core normalizer
# ---------------------------------------------------------------------------

def normalize_vehicle(
    make: Optional[str],
    model: Optional[str],
    year: Optional[int] = None,
) -> NormalizedVehicle:
    """
    Normalize free-form make/model input with typo correction and brand inference.

    Examples:
        ("Vollkswagen", "Gollf")  → NormalizedVehicle("VW", "Golf", corrections=["make: Vollkswagen → VW", "model: Gollf → Golf"])
        (None, "polo")            → NormalizedVehicle("VW", "Polo", corrections=["make inferred from model: VW"])
        ("Golf", None)            → NormalizedVehicle("VW", "Golf", corrections=["make/model swapped and inferred: VW Golf"])
    """
    make = (make or "").strip()
    model = (model or "").strip()
    corrections: list[str] = []

    # ── Step 0: Strip embedded make prefix from model string ──
    # e.g. model="BMW 2er" → make="BMW", model="2er"
    if model and not make:
        for known_make in KNOWN_MAKES:
            if model.lower().startswith(known_make.lower() + " "):
                extracted_model = model[len(known_make):].strip()
                if extracted_model:
                    corrections.append(f"make extracted from model field: {known_make}")
                    make = known_make
                    model = extracted_model
                    break

    # ── Step 1: If make looks like a model name (make filled, model empty) ──
    if make and not model:
        inferred = MODEL_TO_BRAND.get(make.lower())
        if inferred:
            corrections.append(f"make/model swapped and inferred: {inferred} {_canonical_model(make)}")
            model = _canonical_model(make)
            make = inferred

    # ── Step 2: If model given but make is empty → infer make ──
    if model and not make:
        inferred = MODEL_TO_BRAND.get(model.lower())
        if inferred:
            corrections.append(f"make inferred from model: {inferred}")
            make = inferred
        else:
            # Try fuzzy match on model to find the brand
            model_keys = list(MODEL_TO_BRAND.keys())
            close = difflib.get_close_matches(model.lower(), model_keys, n=1, cutoff=0.7)
            if close:
                corrected_model = close[0]
                inferred = MODEL_TO_BRAND[corrected_model]
                corrections.append(f"make inferred from model (fuzzy): {inferred}")
                corrections.append(f"model: {model} → {_canonical_model(corrected_model)}")
                make = inferred
                model = _canonical_model(corrected_model)

    # ── Step 3: Fuzzy-correct make typos ──
    if make:
        known_lower = [m.lower() for m in KNOWN_MAKES]
        close = difflib.get_close_matches(make.lower(), known_lower, n=1, cutoff=0.60)
        if close:
            idx = known_lower.index(close[0])
            corrected = KNOWN_MAKES[idx]
            if corrected.lower() != make.lower():
                corrections.append(f"make: {make} → {corrected}")
            make = corrected

    # ── Step 3b: Strip redundant "Series" suffix (e.g. "1er Series" → "1er") ──
    import re as _re
    model = _re.sub(r'\s+series$', '', model, flags=_re.IGNORECASE).strip()
    model = _re.sub(r'^(\d+)\s*er\s+series$', r'\1er', model, flags=_re.IGNORECASE).strip()

    # ── Step 4: Fuzzy-correct model typos against known models for this make ──
    if model:
        # Collect all known models for this make
        this_make_models = [
            m for m, b in MODEL_TO_BRAND.items()
            if b.lower() == make.lower()
               or (make.lower() in ("vw", "volkswagen") and b == "VW")
        ]
        if this_make_models:
            close = difflib.get_close_matches(model.lower(), this_make_models, n=1, cutoff=0.60)
            if close:
                corrected = _canonical_model(close[0])
                if corrected.lower() != model.lower():
                    corrections.append(f"model: {model} → {corrected}")
                model = corrected

    # ── Normalize casing ──
    make = _canonical_make(make)
    model = _canonical_model(model)

    return NormalizedVehicle(make=make, model=model, year=year, corrections=corrections)


def _canonical_make(make: str) -> str:
    """Return the properly-cased version of the make."""
    for m in KNOWN_MAKES:
        if m.lower() == make.lower():
            return m
    return make.title() if make else make


def _canonical_model(model: str) -> str:
    """Title-case model, preserving known uppercase tokens (GTI, TDI, etc.)."""
    alias = _MODEL_ALIASES.get(model.lower())
    if alias:
        return alias
    # Preserve all-caps tokens (GTI, TDI, GTE, etc.)
    tokens = model.split()
    result = []
    for t in tokens:
        if t.upper() in ("GTI", "GTE", "TDI", "TSI", "SDI", "FSI", "TFSI",
                          "TDI", "CDI", "HDI", "PHEV", "EV", "HEV", "SUV"):
            result.append(t.upper())
        else:
            result.append(t.capitalize())
    return " ".join(result) if result else model
