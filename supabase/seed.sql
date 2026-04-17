-- Carlover Seed Data — German market vehicles
-- Run after schema.sql

-- ------------------------------------------------------------------ --
-- Vehicles
-- ------------------------------------------------------------------ --
INSERT INTO vehicles (make, model, year, engine, transmission, fuel_type, notes) VALUES
    ('VW',       'Golf',      2017, '1.5 TSI',     'DSG',      'Benzin',  'Golf 7 Facelift'),
    ('VW',       'Golf',      2020, '2.0 TDI',     'DSG',      'Diesel',  'Golf 8'),
    ('VW',       'Golf',      2014, '1.4 TSI',     'Manuell',  'Benzin',  'Golf 7'),
    ('BMW',      '3er',       2018, '320d',         'Automatik','Diesel',  'F30 Facelift'),
    ('BMW',      '3er',       2021, '330i',         'Automatik','Benzin',  'G20'),
    ('Mercedes', 'C-Klasse',  2016, 'C220d',        'Automatik','Diesel',  'W205'),
    ('Mercedes', 'C-Klasse',  2019, 'C200',         'Automatik','Benzin',  'W205 Facelift'),
    ('Audi',     'A4',        2017, '2.0 TDI',      'DSG',      'Diesel',  'B9'),
    ('Audi',     'A4',        2020, '2.0 TFSI',     'DSG',      'Benzin',  'B9 Facelift'),
    ('Opel',     'Astra',     2015, '1.6 CDTI',     'Manuell',  'Diesel',  'K'),
    ('Opel',     'Astra',     2019, '1.2 Turbo',    'Manuell',  'Benzin',  'K Facelift'),
    ('Ford',     'Focus',     2018, '1.5 EcoBoost', 'Manuell',  'Benzin',  'Mk4'),
    ('Toyota',   'Corolla',   2020, '1.8 Hybrid',   'CVT',      'Hybrid',  'E210'),
    ('VW',       'Passat',    2016, '2.0 TDI',      'DSG',      'Diesel',  'B8'),
    ('BMW',      '5er',       2019, '520d',         'Automatik','Diesel',  'G30');

-- ------------------------------------------------------------------ --
-- Weaknesses (linked to first few vehicles by row order, using subquery)
-- ------------------------------------------------------------------ --
INSERT INTO weaknesses (vehicle_id, component, description, severity, source)
SELECT id, 'DSG-Getriebe', 'Ruckeln beim Anfahren bei Kaltstart, besonders im Stadtverkehr', 'medium', 'ADAC'
FROM vehicles WHERE make='VW' AND model='Golf' AND year=2017;

INSERT INTO weaknesses (vehicle_id, component, description, severity, source)
SELECT id, 'Kühlmittelausgleichsbehälter', 'Undichtigkeit führt zu Kühlmittelverlust beim 1.5 TSI', 'high', 'Werkstattdaten'
FROM vehicles WHERE make='VW' AND model='Golf' AND year=2017;

INSERT INTO weaknesses (vehicle_id, component, description, severity, source)
SELECT id, 'Abgasanlage (AdBlue)', 'AdBlue-System-Fehler bei niedrigen Temperaturen unter -5°C', 'medium', 'ADAC'
FROM vehicles WHERE make='VW' AND model='Golf' AND year=2020;

INSERT INTO weaknesses (vehicle_id, component, description, severity, source)
SELECT id, 'Steuerkette N47', 'Steuerkettenverschleiß im N47-Motor ab ca. 120.000 km möglich', 'high', 'BMW-Service'
FROM vehicles WHERE make='BMW' AND model='3er' AND year=2018;

INSERT INTO weaknesses (vehicle_id, component, description, severity, source)
SELECT id, 'Kurbelwellenentlüfter', 'Ölverlust durch defekten Kurbelwellenentlüfter beim 2.0 TFSI', 'high', 'ADAC'
FROM vehicles WHERE make='Audi' AND model='A4' AND year=2017;

INSERT INTO weaknesses (vehicle_id, component, description, severity, source)
SELECT id, 'Getriebesteuergerät', '7G-Tronic Steuergerät kann nach 100.000 km Fehler zeigen', 'high', 'Mercedes-Werkstatt'
FROM vehicles WHERE make='Mercedes' AND model='C-Klasse' AND year=2016;

-- ------------------------------------------------------------------ --
-- Service Cases
-- ------------------------------------------------------------------ --
INSERT INTO service_cases (vehicle_id, mileage, issue_type, resolution, cost_eur)
SELECT id, 45000, 'Bremsbeläge', 'Bremsbeläge vorne und hinten gewechselt, Scheiben geprüft', 380.00
FROM vehicles WHERE make='VW' AND model='Golf' AND year=2017;

INSERT INTO service_cases (vehicle_id, mileage, issue_type, resolution, cost_eur)
SELECT id, 78000, 'DSG-Service', 'DSG-Öl gewechselt, Kupplungsadaption zurückgesetzt', 450.00
FROM vehicles WHERE make='VW' AND model='Golf' AND year=2017;

INSERT INTO service_cases (vehicle_id, mileage, issue_type, resolution, cost_eur)
SELECT id, 130000, 'Steuerkette', 'Steuerkette und Spanner vorsorglich gewechselt', 1200.00
FROM vehicles WHERE make='BMW' AND model='3er' AND year=2018;

-- ------------------------------------------------------------------ --
-- Issue Patterns
-- ------------------------------------------------------------------ --
INSERT INTO issue_patterns (makes, models, pattern_name, symptoms, root_cause, solution) VALUES
    (ARRAY['VW'], ARRAY['Golf', 'Passat', 'Tiguan'], 'DSG-Ruckeln',
     ARRAY['Ruckeln beim Anfahren', 'Zögern bei niedrigen Geschwindigkeiten', 'Schaltruck bei Kaltstart'],
     'DSG-Mechatronik-Verschleiß oder Kupplungsadaption nicht korrekt',
     'DSG-Adaptierung zurücksetzen, Getriebeöl wechseln. Bei Wiederholung: Mechatronik prüfen.'),

    (ARRAY['BMW'], ARRAY['3er', '5er', '1er'], 'N47-Steuerkette',
     ARRAY['Kettengeklappper beim Kaltstart', 'Rasseln bei niedrigen Drehzahlen'],
     'Steuerkettenverschleiß im N47-Dieselmotor, typisch ab 150.000 km',
     'Steuerkette mit Spanner und Gleitschienen tauschen. Sofortige Werkstattvorstellung.'),

    (ARRAY['Mercedes'], ARRAY['C-Klasse', 'E-Klasse'], '7G-Tronic-Fehler',
     ARRAY['Schaltruck', 'Getriebe schaltet nicht hoch', 'Fehlermeldung im Armaturenbrett'],
     'Getriebesteuergerät (TCM) defekt oder Getriebeöl kontaminiert',
     'Fehlercode auslesen. Getriebeöl wechseln. Ggf. TCM tauschen (teuer, ~1500 EUR).'),

    (ARRAY['Audi', 'VW'], ARRAY['A4', 'A3', 'Golf', 'Passat'], 'TFSI-Ölverbrauch',
     ARRAY['Erhöhter Ölverbrauch', 'Ölstand sinkt schneller als normal', 'Blaue Abgase'],
     'Kolbenringe verschlissen oder Kurbelwellenentlüfter defekt (2.0 TFSI)',
     'Ölverbrauch messen (max. 0.5L/1000km normal). Kurbelwellenentlüfter prüfen und ggf. tauschen.'),

    (ARRAY['VW', 'Audi', 'Skoda', 'Seat'], ARRAY['Golf', 'Polo', 'Fabia', 'Ibiza'], 'TSI-Steuerkette',
     ARRAY['Rasseln beim Kaltstart', 'Motorwarnleuchte', 'Leistungsverlust'],
     'Steuerkettenverschleiß beim EA211 1.0/1.2/1.4 TSI-Motor',
     'Umgehend Werkstatt aufsuchen. Steuerkette tauschen — Motorschaden möglich bei Weiterfahrt.');

-- ------------------------------------------------------------------ --
-- Demo Questions (for eval and smoke tests)
-- ------------------------------------------------------------------ --
INSERT INTO demo_questions (question, expected_intent, vehicle_json, ground_truth_answer) VALUES
    ('Mein VW Golf 7 2017 macht ein Quietschgeräusch beim Bremsen', 'diagnosis',
     '{"make": "VW", "model": "Golf", "year": 2017}',
     'Das Quietschgeräusch beim Bremsen deutet auf verschlissene Bremsbeläge hin. Empfehlung: Bremsbeläge und -scheiben prüfen lassen.'),

    ('Was sind typische Probleme beim BMW 3er F30?', 'lookup',
     '{"make": "BMW", "model": "3er"}',
     'Bekannte Probleme: N47-Steuerkettenverschleiß (Diesel), Kühlsystem-Thermostat, erhöhter Ölverbrauch beim N20 (320i).'),

    ('Mein Auto ruckelt beim Anfahren', 'diagnosis', NULL,
     'Ruckeln beim Anfahren hat mehrere mögliche Ursachen: DSG-Getriebe, Zündkerzen, Einspritzanlage. Fahrzeugangabe notwendig für genaue Diagnose.'),

    ('Was bedeutet die Motorwarnleuchte?', 'general', NULL,
     'Die Motorwarnleuchte (MIL) zeigt einen Fehler im Motor- oder Abgassystem an. OBD-Auslesung notwendig. Sofort zur Werkstatt.'),

    ('Wie oft muss ein VW Golf 7 zur Inspektion?', 'lookup',
     '{"make": "VW", "model": "Golf", "year": 2017}',
     'VW empfiehlt alle 15.000 km oder 12 Monate (je nachdem, was zuerst zutrifft). Große Inspektion alle 30.000 km.'),

    ('Mein Audi A4 2017 verliert Öl', 'diagnosis',
     '{"make": "Audi", "model": "A4", "year": 2017}',
     'Beim Audi A4 B9 mit 2.0 TFSI ist Ölverlust am Kurbelwellenentlüfter ein bekanntes Problem. Werkstattdiagnose empfohlen.'),

    ('Was kostet ein DSG-Ölwechsel beim Golf?', 'lookup',
     '{"make": "VW", "model": "Golf"}',
     'Ein DSG-Ölwechsel beim VW Golf kostet in der Regel 300–500 EUR, je nach Werkstatt und DSG-Typ (6- oder 7-Gang).'),

    ('Mein Mercedes C200 startet nicht mehr', 'diagnosis',
     '{"make": "Mercedes", "model": "C-Klasse"}',
     'Startprobleme können viele Ursachen haben: Batterie, Anlasser, Kraftstoffpumpe. OBD-Auslesung empfohlen.'),

    ('Ist der Toyota Corolla Hybrid zuverlässig?', 'lookup',
     '{"make": "Toyota", "model": "Corolla"}',
     'Der Toyota Corolla Hybrid gilt als sehr zuverlässig. Hybridbatterie typisch 150.000–200.000 km. Geringer Kraftstoffverbrauch in der Stadt.'),

    ('Mein Auto macht ein Klopfgeräusch beim Fahren', 'diagnosis', NULL,
     'Klopfgeräusche können auf Motorprobleme (Klopfen), Fahrwerksprobleme oder Auspuffanlage hindeuten. Bitte Fahrzeug angeben.');
