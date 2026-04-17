# Vehicle Lookup — Knowledge Policy

## German Market Focus

This system is optimized for the German automotive market. Common makes and models:

- **VW**: Golf (4–8, GTI, R, GTE), Polo, Passat, Tiguan, T-Roc, ID.3, ID.4
- **BMW**: 1er, 2er, 3er, 4er, 5er, X1, X3, X5, M-Modelle
- **Mercedes**: A-Klasse, B-Klasse, C-Klasse, E-Klasse, GLC, GLE
- **Audi**: A3, A4, A6, Q3, Q5, Q7, e-tron
- **Opel**: Astra, Corsa, Insignia, Grandland, Mokka
- **Ford**: Fiesta, Focus, Kuga, Puma
- **Toyota**: Yaris, Corolla, RAV4, Prius (Hybrid)

## Entity Extraction Guidelines

When extracting vehicle information:
1. Map common abbreviations: "3er" → BMW 3er, "Golf VII" or "Golf 7" → VW Golf (Gen 7)
2. Use year hints to narrow generation: 2013–2020 = Golf 7, 2020+ = Golf 8
3. Variants matter: GTI, TDI, TSI, xDrive, TFSI, AMG, M affect known issues
4. Generation ranges (examples):
   - VW Golf 7: 2012–2020
   - VW Golf 8: 2020–present
   - BMW F30 (3er): 2012–2019
   - BMW G20 (3er): 2019–present
   - Mercedes W205 (C-Klasse): 2014–2022

## Confidence Scoring Guidelines

- Year provided + matches a known generation → confidence 0.85–0.95
- No year, but make/model unambiguous → confidence 0.65–0.80
- Ambiguous model name (multiple variants) → confidence 0.40–0.65, list candidates
- Unknown make/model → confidence < 0.40, ask for clarification

## When to Ask for Clarification

Ask if:
- Make AND model are both missing
- Model matches multiple generations with different known issues
- Variant significantly affects diagnosis (e.g., TDI vs TSI for engine issues)
